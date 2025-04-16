# p2p_network_improved.py

import json
import socket
import threading
import time
import random
import hashlib
from typing import List, Dict, Any, Callable, Optional
import requests
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature
from node_discovery import NodeDiscovery



class P2PNodeImproved:
    """改进的P2P网络节点类，使用以太坊风格的节点发现"""
    
    def __init__(self, host: str, port: int, node_id: str, blockchain, bootstrap_nodes=None):
        """
        初始化P2P节点
        
        Args:
            host: 主机地址
            port: 端口号
            node_id: 节点ID
            blockchain: 区块链实例
            bootstrap_nodes: 引导节点列表 [(host, port), ...]
        """
        self.host = host
        self.port = port
        self.node_id = node_id
        self.blockchain = blockchain
        self.running = False
        
        # 初始化节点发现
        self.discovery = NodeDiscovery(node_id, host, port, bootstrap_nodes)
        
        # 消息处理器
        self.message_handlers = {
            'HANDSHAKE': self._handle_handshake,
            'BLOCKCHAIN_REQUEST': self._handle_blockchain_request,
            'NEW_BLOCK': self._handle_new_block,
            'NEW_TRANSACTION': self._handle_new_transaction,
            'BLOCK_REQUEST': self._handle_block_request,
            'BLOCK_CONFIRMATION': self._handle_block_confirmation
        }
    
    def start(self) -> None:
        """启动P2P节点"""
        self.running = True
        
        # 启动节点发现服务器
        self.discovery.start_discovery_server()
        
        # 启动P2P服务器
        self._start_p2p_server()
        
        # 从引导节点开始发现网络
        threading.Thread(target=self.discovery.bootstrap, daemon=True).start()
        
        # 启动定期刷新
        self.discovery.start_refresh_timer()
        
        print(f"P2P节点 {self.node_id} 启动，监听 {self.host}:{self.port}")
    
    def _start_p2p_server(self) -> None:
        """启动P2P服务器"""
        # 创建服务器套接字
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port + 1))  # 使用不同的端口
        server_socket.listen(10)
        
        # 启动处理连接的线程
        threading.Thread(target=self._handle_p2p_connections, args=(server_socket,), daemon=True).start()
    
    def _handle_p2p_connections(self, server_socket: socket.socket) -> None:
        """处理P2P连接"""
        while self.running:
            try:
                client_socket, address = server_socket.accept()
                threading.Thread(target=self._handle_p2p_request, args=(client_socket,), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"处理P2P连接时出错: {e}")
    
    def _handle_p2p_request(self, client_socket: socket.socket) -> None:
        """处理P2P请求"""
        try:
            # 接收请求
            data = client_socket.recv(4096)
            if not data:
                return
            
            message = json.loads(data.decode('utf-8'))
            message_type = message['type']
            
            # 处理不同类型的消息
            if message_type in self.message_handlers:
                response = self.message_handlers[message_type](message)
                if response:
                    client_socket.send(json.dumps(response).encode('utf-8'))
            else:
                print(f"未知的消息类型: {message_type}")
        
        except Exception as e:
            print(f"处理P2P请求时出错: {e}")
        finally:
            client_socket.close()
    
    def _handle_handshake(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """处理握手消息"""
        # 添加节点
        from_node = message['from']
        self.discovery.add_node(from_node['node_id'], from_node['host'], from_node['port'])
        
        # 创建响应
        response = {
            'type': 'HANDSHAKE',
            'from': {
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port
            },
            'timestamp': time.time()
        }
        
        return response
    
    def _handle_blockchain_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """处理区块链请求消息"""
        # 创建响应
        response = {
            'type': 'BLOCKCHAIN_RESPONSE',
            'from': {
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port
            },
            'blockchain': self.blockchain.to_dict(),
            'timestamp': time.time()
        }
        
        return response
    
    def _handle_new_block(self, message: Dict[str, Any]) -> None:
        """处理新区块消息"""
        # 从消息中提取区块
        block_dict = message['block']
        
        try:
            # 将字典转换为区块对象
            # 注意：这里需要根据你的区块链实现进行适配
            block = self.blockchain.create_block_from_dict(block_dict)
            
            # 验证区块
            if self.blockchain.is_valid_block(block):
                # 添加区块到链中
                success = self.blockchain.add_block(block)
                
                if success:
                    print(f"成功添加新区块: {block.hash}")
                    
                    # 广播确认消息
                    self.broadcast_message('BLOCK_CONFIRMATION', {
                        'block_hash': block.hash,
                        'status': 'accepted'
                    })
                else:
                    print(f"无法添加区块: {block.hash}")
            else:
                print(f"收到无效区块: {block_dict.get('hash', 'unknown')}")
        except Exception as e:
            print(f"处理新区块时出错: {e}")
        
        return None
    
    def _handle_new_transaction(self, message: Dict[str, Any]) -> None:
        """处理新交易消息"""
        # 从消息中提取交易
        transaction_dict = message['transaction']
        
        try:
            # 将字典转换为交易对象
            # 注意：这里需要根据你的区块链实现进行适配
            transaction = self.blockchain.create_transaction_from_dict(transaction_dict)
            
            # 验证交易
            if self.blockchain.is_valid_transaction(transaction):
                # 添加交易到内存池
                success = self.blockchain.add_transaction(transaction)
                
                if success:
                    print(f"成功添加新交易: {transaction.id}")
                else:
                    print(f"无法添加交易: {transaction.id}")
            else:
                print(f"收到无效交易: {transaction_dict.get('id', 'unknown')}")
        except Exception as e:
            print(f"处理新交易时出错: {e}")
        
        return None
    
    def _handle_block_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """处理区块请求消息"""
        # 获取请求的区块范围
        start_index = message['start_index']
        end_index = message['end_index']
        
        # 获取请求的区块
        requested_blocks = []
        for i in range(start_index, end_index + 1):
            if i < len(self.blockchain.chain):
                requested_blocks.append(self.blockchain.chain[i].to_dict())
        
        # 创建响应
        response = {
            'type': 'BLOCK_RESPONSE',
            'from': {
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port
            },
            'blocks': requested_blocks,
            'timestamp': time.time()
        }
        
        return response
    
    def _handle_block_confirmation(self, message: Dict[str, Any]) -> None:
        """处理区块确认消息"""
        # 获取区块哈希和状态
        block_hash = message['block_hash']
        status = message['status']
        
        try:
            # 更新区块状态
            if status == 'accepted':
                # 可以在这里实现一个计数器，记录有多少节点确认了这个区块
                # 如果超过一定数量，可以认为区块已经被网络接受
                print(f"区块 {block_hash} 被节点 {message['from']['node_id']} 确认")
            else:
                print(f"区块 {block_hash} 被节点 {message['from']['node_id']} 拒绝")
        except Exception as e:
            print(f"处理区块确认时出错: {e}")
        
        return None
    
    def connect_to_peer(self, host: str, port: int) -> bool:
        """连接到对等节点"""
        try:
            # 创建客户端套接字
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5)  # 设置超时时间
            client_socket.connect((host, port + 1))  # 连接到P2P端口
            
            # 创建握手消息
            handshake_message = {
                'type': 'HANDSHAKE',
                'from': {
                    'node_id': self.node_id,
                    'host': self.host,
                    'port': self.port
                },
                'timestamp': time.time()
            }
            
            # 发送消息
            client_socket.send(json.dumps(handshake_message).encode('utf-8'))
            
            # 接收响应
            response = client_socket.recv(4096).decode('utf-8')
            response_data = json.loads(response)
            
            # 验证响应类型
            if response_data['type'] == 'HANDSHAKE':
                # 添加节点
                from_node = response_data['from']
                self.discovery.add_node(from_node['node_id'], from_node['host'], from_node['port'])
                
                print(f"成功连接到节点 {host}:{port}")
                return True
            
            return False
        except Exception as e:
            print(f"连接到节点 {host}:{port} 失败: {e}")
            return False
        finally:
            client_socket.close()
    
    def broadcast_message(self, message_type: str, data: Dict[str, Any]) -> None:
        """广播消息到所有已知节点"""
        # 创建消息
        message = {
            'type': message_type,
            'from': {
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port
            },
            **data,
            'timestamp': time.time()
        }
        
        # 获取所有已知节点
        all_nodes = []
        for bucket in self.discovery.node_buckets:
            all_nodes.extend(bucket)
        
        # 广播消息
        for node in all_nodes:
            try:
                # 创建客户端套接字
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(5)  # 设置超时时间
                client_socket.connect((node['host'], node['port'] + 1))  # 连接到P2P端口
                
                # 发送消息
                client_socket.send(json.dumps(message).encode('utf-8'))
                client_socket.close()
                
                # 更新节点的最后见到时间
                node['last_seen'] = time.time()
                
            except Exception as e:
                print(f"向节点 {node['node_id']} 广播消息失败: {e}")
    
    def broadcast_new_block(self, block) -> None:
        """广播新区块"""
        self.broadcast_message('NEW_BLOCK', {'block': block.to_dict()})
    
    def broadcast_new_transaction(self, transaction) -> None:
        """广播新交易"""
        self.broadcast_message('NEW_TRANSACTION', {'transaction': transaction.to_dict()})
    
    def request_blockchain(self, node_id: str) -> bool:
        """请求区块链数据"""
        # 查找节点
        node = None
        for bucket in self.discovery.node_buckets:
            for n in bucket:
                if n['node_id'] == node_id:
                    node = n
                    break
            if node:
                break
        
        if not node:
            print(f"节点 {node_id} 不存在")
            return False
        
        try:
            # 创建客户端套接字
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10)  # 设置超时时间
            client_socket.connect((node['host'], node['port'] + 1))  # 连接到P2P端口
            
            # 创建请求消息
            request_message = {
                'type': 'BLOCKCHAIN_REQUEST',
                'from': {
                    'node_id': self.node_id,
                    'host': self.host,
                    'port': self.port
                },
                'timestamp': time.time()
            }
            
            # 发送消息
            client_socket.send(json.dumps(request_message).encode('utf-8'))
            
            # 接收响应
            response = client_socket.recv(4096).decode('utf-8')
            response_data = json.loads(response)
            
            # 验证响应类型
            if response_data['type'] == 'BLOCKCHAIN_RESPONSE':
                # 处理区块链数据
                # 这里需要根据你的区块链实现进行适配
                # ...
                
                return True
            
            return False
        except Exception as e:
            print(f"请求区块链数据失败: {e}")
            return False
        finally:
            client_socket.close()
    
    def synchronize_blockchain(self) -> bool:
        """同步区块链"""
        # 获取所有已知节点
        all_nodes = []
        for bucket in self.discovery.node_buckets:
            all_nodes.extend(bucket)
        
        if not all_nodes:
            print("没有已知节点可同步")
            return False
        
        # 随机选择几个节点
        sample_size = min(3, len(all_nodes))
        selected_nodes = random.sample(all_nodes, sample_size)
        
        success = False
        for node in selected_nodes:
            try:
                # 创建客户端套接字
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(10)  # 设置超时时间
                client_socket.connect((node['host'], node['port'] + 1))  # 连接到P2P端口
                
                # 创建请求消息
                request_message = {
                    'type': 'BLOCKCHAIN_REQUEST',
                    'from': {
                        'node_id': self.node_id,
                        'host': self.host,
                        'port': self.port
                    },
                    'timestamp': time.time()
                }
                
                # 发送消息
                client_socket.send(json.dumps(request_message).encode('utf-8'))
                
                # 接收响应
                response = client_socket.recv(4096).decode('utf-8')
                response_data = json.loads(response)
                
                # 验证响应类型
                if response_data['type'] == 'BLOCKCHAIN_RESPONSE':
                    # 处理区块链数据
                    blockchain_data = response_data['blockchain']
                    
                    # 验证接收到的区块链
                    if self.blockchain.validate_chain(blockchain_data):
                        # 如果接收到的链比当前链长，则替换
                        if len(blockchain_data['chain']) > len(self.blockchain.chain):
                            # 替换区块链
                            self.blockchain.replace_chain(blockchain_data)
                            print(f"成功从节点 {node['node_id']} 同步区块链")
                            success = True
                        else:
                            print(f"当前区块链已是最新")
                    else:
                        print(f"从节点 {node['node_id']} 接收到的区块链无效")
                
                client_socket.close()
                
                if success:
                    break
                    
            except Exception as e:
                print(f"从节点 {node['node_id']} 同步区块链失败: {e}")
        
        return success
    
    def stop(self) -> None:
        """停止P2P节点"""
        self.running = False
        print(f"P2P节点 {self.node_id} 已停止")