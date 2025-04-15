

# p2p_network.py

import json
import socket
import threading
import time
from typing import List, Dict, Any, Callable, Optional
import random

from blockchain_core import Blockchain, Block, Transaction

class Message:
    """P2P网络消息类"""
    
    # 消息类型
    TYPE_HANDSHAKE = "HANDSHAKE"
    TYPE_DISCOVER = "DISCOVER"
    TYPE_BLOCKCHAIN_REQUEST = "BLOCKCHAIN_REQUEST"
    TYPE_BLOCKCHAIN_RESPONSE = "BLOCKCHAIN_RESPONSE"
    TYPE_NEW_BLOCK = "NEW_BLOCK"
    TYPE_NEW_TRANSACTION = "NEW_TRANSACTION"
    TYPE_BLOCK_REQUEST = "BLOCK_REQUEST"
    TYPE_BLOCK_RESPONSE = "BLOCK_RESPONSE"
    
    def __init__(self, msg_type: str, data: Dict[str, Any], sender: str):
        """
        初始化消息
        
        Args:
            msg_type: 消息类型
            data: 消息数据
            sender: 发送者节点ID
        """
        self.type = msg_type
        self.data = data
        self.sender = sender
        self.timestamp = time.time()
    
    def to_json(self) -> str:
        """将消息转换为JSON字符串"""
        return json.dumps({
            'type': self.type,
            'data': self.data,
            'sender': self.sender,
            'timestamp': self.timestamp
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """从JSON字符串创建消息对象"""
        msg_dict = json.loads(json_str)
        message = cls(
            msg_type=msg_dict['type'],
            data=msg_dict['data'],
            sender=msg_dict['sender']
        )
        message.timestamp = msg_dict['timestamp']
        return message


class P2PNode:
    """P2P网络节点类"""
    
    def __init__(self, host: str, port: int, node_id: str, blockchain: Blockchain):
        """
        初始化P2P节点
        
        Args:
            host: 主机地址
            port: 端口号
            node_id: 节点ID
            blockchain: 区块链实例
        """
        self.host = host
        self.port = port
        self.node_id = node_id
        self.blockchain = blockchain
        self.peers = {}  # 格式: {node_id: (host, port)}
        self.server_socket = None
        self.running = False
        self.syncing = True
        self.time_offset = 0  # 时间偏移量
        self.time_samples = []  # 时间样本
        self.max_time_samples = 10  # 最大样本数
    
        self.message_handlers = {
            Message.TYPE_HANDSHAKE: self.handle_handshake,
            Message.TYPE_DISCOVER: self.handle_discover,
            Message.TYPE_BLOCKCHAIN_REQUEST: self.handle_blockchain_request,
            Message.TYPE_BLOCKCHAIN_RESPONSE: self.handle_blockchain_response,
            Message.TYPE_NEW_BLOCK: self.handle_new_block,
            Message.TYPE_NEW_TRANSACTION: self.handle_new_transaction
        }
    
    def start(self) -> None:
        """启动P2P节点"""
        # 创建服务器套接字
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        
        self.running = True
        
        # 启动监听线程
        threading.Thread(target=self.listen_for_connections, daemon=True).start()

        # 启动同步定时器
        threading.Timer(5, self.start_sync_timer).start()

        print(f"节点 {self.node_id} 启动，监听 {self.host}:{self.port}")

    def start_sync_timer(self):
        """启动定期同步定时器"""
        if not self.peers:
            # 没有对等节点，稍后重试
            threading.Timer(10, self.start_sync_timer).start()
            return
        
        # 执行同步
        self.synchronize_blockchain()
        
        # 设置下一次同步
        threading.Timer(60, self.start_sync_timer).start()

    def stop(self) -> None:
        """停止P2P节点"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print(f"节点 {self.node_id} 已停止")
    
    def listen_for_connections(self) -> None:
        """监听连接请求"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                threading.Thread(target=self.handle_connection, args=(client_socket,), daemon=True).start()
                print(f"接受来自 {address} 的连接")
            except Exception as e:
                if self.running:
                    print(f"监听连接时出错: {e}")
    
    def handle_connection(self, client_socket: socket.socket) -> None:
        """
        处理客户端连接
        
        Args:
            client_socket: 客户端套接字
        """
        try:
            # 接收消息
            data = client_socket.recv(4096)
            if data:
                message = Message.from_json(data.decode('utf-8'))
                print(f"收到来自 {message.sender} 的消息: {message.type}")
                
                # 处理消息
                if message.type in self.message_handlers:
                    response = self.message_handlers[message.type](message)
                    if response:
                        client_socket.send(response.encode('utf-8'))
        except Exception as e:
            print(f"处理连接时出错: {e}")
        finally:
            client_socket.close()
    
    def connect_to_peer(self, host: str, port: int) -> bool:
        """
        连接到对等节点
        
        Args:
            host: 对等节点主机地址
            port: 对等节点端口号
            
        Returns:
            bool: 连接是否成功
        """
        try:
            # 创建客户端套接字
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((host, port))
            
            # 发送握手消息
            handshake_message = Message(
                Message.TYPE_HANDSHAKE,
                {
                    'node_id': self.node_id,
                    'host': self.host,
                    'port': self.port
                },
                self.node_id
            )
            
            client_socket.send(handshake_message.to_json().encode('utf-8'))
            
            # 接收响应
            response = client_socket.recv(4096).decode('utf-8')
            response_message = Message.from_json(response)
            
            if response_message.type == Message.TYPE_HANDSHAKE:
                peer_id = response_message.data['node_id']
                peer_host = response_message.data['host']
                peer_port = response_message.data['port']
                
                # 添加对等节点
                self.peers[peer_id] = (peer_host, peer_port)
                print(f"已连接到节点 {peer_id} ({peer_host}:{peer_port})")
                
                # 请求区块链数据
                self.request_blockchain(peer_id)
                
                return True
            else:
                print(f"握手失败: {response_message.type}")
                return False
        except Exception as e:
            print(f"连接到对等节点时出错: {e}")
            return False
        finally:
            client_socket.close()
    
    def broadcast_message(self, message: Message) -> None:
        """
        向所有对等节点广播消息
        
        Args:
            message: 要广播的消息
        """
        for peer_id, (host, port) in self.peers.items():
            try:
                # 创建客户端套接字
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((host, port))
                
                # 发送消息
                client_socket.send(message.to_json().encode('utf-8'))
                client_socket.close()
                
                print(f"向节点 {peer_id} 广播消息: {message.type}")
            except Exception as e:
                print(f"向节点 {peer_id} 广播消息时出错: {e}")
    
    def send_message_to_peer(self, peer_id: str, message: Message) -> Optional[Message]:
        """
        向特定对等节点发送消息
        
        Args:
            peer_id: 对等节点ID
            message: 要发送的消息
            
        Returns:
            Optional[Message]: 响应消息，如果有的话
        """
        if peer_id not in self.peers:
            print(f"节点 {peer_id} 不在对等节点列表中")
            return None
        
        host, port = self.peers[peer_id]
        
        try:
            # 创建客户端套接字
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((host, port))
            
            # 发送消息
            client_socket.send(message.to_json().encode('utf-8'))
            
            # 接收响应
            response = client_socket.recv(4096).decode('utf-8')
            response_message = Message.from_json(response)
            
            print(f"向节点 {peer_id} 发送消息: {message.type}，收到响应: {response_message.type}")
            
            return response_message
        except Exception as e:
            print(f"向节点 {peer_id} 发送消息时出错: {e}")
            return None
        finally:
            client_socket.close()
    
    def handle_handshake(self, message: Message) -> str:
        """
        处理握手消息
        
        Args:
            message: 握手消息
            
        Returns:
            str: 响应消息的JSON字符串
        """
        peer_id = message.data['node_id']
        peer_host = message.data['host']
        peer_port = message.data['port']
        
        # 添加对等节点
        self.peers[peer_id] = (peer_host, peer_port)
        print(f"已添加节点 {peer_id} ({peer_host}:{peer_port})")
        
        # 创建响应消息
        response_message = Message(
            Message.TYPE_HANDSHAKE,
            {
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port
            },
            self.node_id
        )
        
        return response_message.to_json()
    
    def handle_discover(self, message: Message) -> str:
        """
        处理发现消息
        
        Args:
            message: 发现消息
            
        Returns:
            str: 响应消息的JSON字符串
        """
        # 创建响应消息，包含所有已知的对等节点
        response_message = Message(
            Message.TYPE_DISCOVER,
            {
                'peers': {pid: {'host': host, 'port': port} for pid, (host, port) in self.peers.items()}
            },
            self.node_id
        )
        
        return response_message.to_json()
    
    def handle_blockchain_request(self, message: Message) -> str:
        """
        处理区块链请求消息
        
        Args:
            message: 区块链请求消息
            
        Returns:
            str: 响应消息的JSON字符串
        """
        # 创建响应消息，包含整个区块链
        response_message = Message(
            Message.TYPE_BLOCKCHAIN_RESPONSE,
            {
                'blockchain': self.blockchain.to_dict()
            },
            self.node_id
        )
        
        return response_message.to_json()
    
    def handle_blockchain_response(self, message: Message) -> None:
        """
        处理区块链响应消息
        
        Args:
            message: 区块链响应消息
        """
        received_blockchain = Blockchain.from_dict(message.data['blockchain'])
        
        # 如果接收到的区块链比当前区块链长，则替换当前区块链
        if len(received_blockchain.chain) > len(self.blockchain.chain):
            if received_blockchain.is_chain_valid():
                self.blockchain = received_blockchain
                print(f"从节点 {message.sender} 更新区块链，当前长度: {len(self.blockchain.chain)}")
            else:
                print(f"从节点 {message.sender} 接收到的区块链无效")
    
    def handle_new_block(self, message: Message) -> None:
        """
        处理新区块消息
        
        Args:
            message: 新区块消息
        """
        block_dict = message.data['block']
        new_block = Block.from_dict(block_dict)
        
        # 检查区块是否已存在
        if any(b.hash == new_block.hash for b in self.blockchain.chain):
            print(f"区块 {new_block.index} 已存在，忽略")
            return None
        
        # 检查区块索引是否连续
        expected_index = len(self.blockchain.chain)
        if new_block.index > expected_index:
            print(f"收到未来区块 {new_block.index}，当前链长度: {expected_index}")
            # 请求缺失的区块
            self.request_missing_blocks(message.sender, expected_index, new_block.index - 1)
            return None
        
        # 检查区块索引是否小于当前链长度（可能是分叉）
        if new_block.index < expected_index:
            print(f"收到过去区块 {new_block.index}，当前链长度: {expected_index}")
            # 处理可能的分叉
            if self.handle_fork(new_block):
                print(f"接受分叉区块 {new_block.index}")
            else:
                print(f"拒绝分叉区块 {new_block.index}")
            return None
        
        # 验证并添加新区块
        if self.blockchain.is_valid_block(new_block):
            if self.blockchain.add_block(new_block):
                print(f"从节点 {message.sender} 添加新区块: {new_block.index}")

                # 广播确认消息
                confirmation_message = Message(
                    "BLOCK_CONFIRMATION",
                    {'block_hash': new_block.hash},
                    self.node_id
                )
                self.broadcast_message(confirmation_message)
            

                # 广播给其他节点（除了发送者）
                for peer_id in self.peers:
                    if peer_id != message.sender:
                        self.send_message_to_peer(peer_id, message)
            else:
                print(f"从节点 {message.sender} 接收到的区块无效")
        else:
            print(f"从节点 {message.sender} 接收到的区块无效")

    def request_missing_blocks(self, peer_id: str, start_index: int, end_index: int) -> None:
        """
        请求缺失的区块
        
        Args:
            peer_id: 对等节点ID
            start_index: 起始区块索引
            end_index: 结束区块索引
        """
        if peer_id not in self.peers:
            print(f"节点 {peer_id} 不在对等节点列表中")
            return
        
        print(f"向节点 {peer_id} 请求区块 {start_index} 到 {end_index}")
        
        # 创建请求消息
        request_message = Message(
            "BLOCK_REQUEST",
            {
                'start_index': start_index,
                'end_index': end_index
            },
            self.node_id
        )
        
        # 发送请求
        self.send_message_to_peer(peer_id, request_message)

    def handle_block_request(self, message: Message) -> str:
        """
        处理区块请求消息
        
        Args:
            message: 区块请求消息
            
        Returns:
            str: 响应消息的JSON字符串
        """
        start_index = message.data['start_index']
        end_index = message.data['end_index']
        
        # 确保索引在有效范围内
        start_index = max(0, start_index)
        end_index = min(len(self.blockchain.chain) - 1, end_index)
        
        # 获取请求的区块
        requested_blocks = []
        for i in range(start_index, end_index + 1):
            if i < len(self.blockchain.chain):
                requested_blocks.append(self.blockchain.chain[i].to_dict())
        
        # 创建响应消息
        response_message = Message(
            "BLOCK_RESPONSE",
            {
                'blocks': requested_blocks
            },
            self.node_id
        )
        
        return response_message.to_json()

    def handle_block_response(self, message: Message) -> None:
        """
        处理区块响应消息
        
        Args:
            message: 区块响应消息
        """
        blocks_dict = message.data['blocks']
        
        if not blocks_dict:
            print("收到空的区块响应")
            return
        
        # 将区块按索引排序
        blocks = [Block.from_dict(block_dict) for block_dict in blocks_dict]
        blocks.sort(key=lambda b: b.index)
        
        # 检查第一个区块是否与当前链连接
        first_block = blocks[0]
        if first_block.index > 0:
            if first_block.index > len(self.blockchain.chain):
                print(f"收到的区块不连续，期望索引 {len(self.blockchain.chain)}，收到 {first_block.index}")
                return
            
            if first_block.previous_hash != self.blockchain.chain[first_block.index - 1].hash:
                print(f"区块 {first_block.index} 与当前链不连接")
                return
        
        # 逐个添加区块
        for block in blocks:
            if block.index < len(self.blockchain.chain):
                # 已有的区块，检查是否需要处理分叉
                if block.hash != self.blockchain.chain[block.index].hash:
                    self.handle_fork(block)
            else:
                # 新区块，直接添加
                if self.blockchain.is_valid_block(block):
                    if self.blockchain.add_block(block):
                        print(f"从节点 {message.sender} 添加新区块: {block.index}")
                    else:
                        print(f"添加区块 {block.index} 失败")
                else:
                    print(f"区块 {block.index} 验证失败")

    def handle_fork(self, new_block: Block) -> bool:
        """
        处理区块链分叉
        
        Args:
            new_block: 新区块
            
        Returns:
            bool: 是否接受分叉
        """
        # 对于区块1的特殊处理（所有区块1都基于创世区块）
        if new_block.index == 1 and len(self.blockchain.chain) >= 2:
            # 验证新区块是否基于创世区块
            if new_block.previous_hash == self.blockchain.chain[0].hash:
                # 比较当前区块1和新区块1的哈希值，选择较小的哈希值作为胜出者
                current_block1 = self.blockchain.chain[1]
                if new_block.hash < current_block1.hash:
                    # 创建分叉链
                    fork_chain = self.blockchain.chain[:1].copy()  # 只保留创世区块
                    fork_chain.append(new_block)
                    
                    # 将当前链中不在分叉链中的交易添加回待处理交易池
                    for block in self.blockchain.chain[1:]:
                        for tx in block.transactions:
                            if not any(t.transaction_id == tx.transaction_id for t in self.blockchain.pending_transactions):
                                self.blockchain.pending_transactions.append(tx)
                    
                    # 替换当前链
                    self.blockchain.chain = fork_chain
                    print(f"区块链分叉，切换到新链（哈希值较小），长度: {len(self.blockchain.chain)}")
                    return True
                
                print(f"区块链分叉，保留当前链（哈希值较小），长度: {len(self.blockchain.chain)}")
                return False
        # 找到分叉点
        fork_point = -1
        for i in range(len(self.blockchain.chain)):
            if i == new_block.index - 1 and self.blockchain.chain[i].hash == new_block.previous_hash:
                fork_point = i
                break
        
        if fork_point == -1:
            print(f"无法找到分叉点，区块 {new_block.index} 无法添加")
            return False
        
        # 创建分叉链
        fork_chain = self.blockchain.chain[:fork_point + 1].copy()
        fork_chain.append(new_block)
        
        # 如果分叉链比当前链长或具有更高的总难度，则替换当前链
        if len(fork_chain) > len(self.blockchain.chain):
            # 将当前链中不在分叉链中的交易添加回待处理交易池
            for block in self.blockchain.chain[fork_point + 1:]:
                for tx in block.transactions:
                    if not any(t.transaction_id == tx.transaction_id for t in self.blockchain.pending_transactions):
                        self.blockchain.pending_transactions.append(tx)
            
            # 替换当前链
            self.blockchain.chain = fork_chain
            print(f"区块链分叉，切换到新链，长度: {len(self.blockchain.chain)}")
            return True
        
        print(f"区块链分叉，保留当前链，长度: {len(self.blockchain.chain)}")
        return False
    
    def handle_new_transaction(self, message: Message) -> None:
        """
        处理新交易消息
        
        Args:
            message: 新交易消息
        """
        transaction_dict = message.data['transaction']
        new_transaction = Transaction.from_dict(transaction_dict)
        
        # 验证并添加新交易
        if self.blockchain.add_transaction(new_transaction):
            print(f"从节点 {message.sender} 添加新交易: {new_transaction.transaction_id}")
        else:
            print(f"从节点 {message.sender} 接收到的交易无效")
    
    def request_blockchain(self, peer_id: str) -> None:
        """
        向对等节点请求区块链数据
        
        Args:
            peer_id: 对等节点ID
        """
        request_message = Message(
            Message.TYPE_BLOCKCHAIN_REQUEST,
            {},
            self.node_id
        )
        
        self.send_message_to_peer(peer_id, request_message)

    def synchronize_blockchain(self) -> bool:
        """与网络同步区块链"""
        if not self.peers or self.syncing:
            # print("没有对等节点可同步或正在同步中\n")
            return False
        
        self.syncing = True
        
        try:
            # 随机选择一个对等节点
            peer_id = random.choice(list(self.peers.keys()))
            
            # 请求区块链
            request_message = Message(
                Message.TYPE_BLOCKCHAIN_REQUEST,
                {},
                self.node_id
            )
            
            response = self.send_message_to_peer(peer_id, request_message)
            
            if not response or response.type != Message.TYPE_BLOCKCHAIN_RESPONSE:
                print(f"从节点 {peer_id} 同步区块链失败")
                return False
            
            received_blockchain = Blockchain.from_dict(response.data['blockchain'])
            
            # 验证接收到的区块链
            if not received_blockchain.is_chain_valid():
                print(f"从节点 {peer_id} 接收到的区块链无效")
                return False
            
            # 如果接收到的区块链比当前区块链长，则替换当前区块链
            if len(received_blockchain.chain) > len(self.blockchain.chain):
                # 保存当前待处理交易
                pending_transactions = self.blockchain.pending_transactions.copy()
                
                # 替换区块链
                self.blockchain = received_blockchain
                
                # 将原有的待处理交易添加回来（排除已经在新链中的交易）
                for tx in pending_transactions:
                    if not any(block.transactions for block in self.blockchain.chain 
                            if any(t.transaction_id == tx.transaction_id for t in block.transactions)):
                        self.blockchain.pending_transactions.append(tx)
                
                print(f"从节点 {peer_id} 同步区块链成功，当前长度: {len(self.blockchain.chain)}")
                return True
            
            print(f"当前区块链已是最新，长度: {len(self.blockchain.chain)}")
            return True
        finally:
            self.syncing = False

    def broadcast_new_block(self, block: Block) -> None:
        """
        广播新区块
        
        Args:
            block: 新区块
        """
        message = Message(
            Message.TYPE_NEW_BLOCK,
            {
                'block': block.to_dict()
            },
            self.node_id
        )
        
        self.broadcast_message(message)
    
    def broadcast_new_transaction(self, transaction: Transaction) -> None:
        """
        广播新交易
        
        Args:
            transaction: 新交易
        """
        message = Message(
            Message.TYPE_NEW_TRANSACTION,
            {
                'transaction': transaction.to_dict()
            },
            self.node_id
        )
        
        self.broadcast_message(message)
    
    def discover_peers(self, seed_peer_id: str) -> None:
        """
        发现对等节点
        
        Args:
            seed_peer_id: 种子对等节点ID
        """
        if seed_peer_id not in self.peers:
            print(f"种子节点 {seed_peer_id} 不在对等节点列表中")
            return
        
        discover_message = Message(
            Message.TYPE_DISCOVER,
            {},
            self.node_id
        )
        
        response = self.send_message_to_peer(seed_peer_id, discover_message)
        
        if response and response.type == Message.TYPE_DISCOVER:
            new_peers = response.data['peers']
            
            for peer_id, peer_info in new_peers.items():
                if peer_id != self.node_id and peer_id not in self.peers:
                    host = peer_info['host']
                    port = peer_info['port']
                    
                    # 连接到新发现的对等节点
                    self.connect_to_peer(host, port)
    
    def broadcast_block_confirmation(self, block_hash: str) -> None:
        """
        广播区块确认
        
        Args:
            block_hash: 区块哈希
        """
        message = Message(
            "BLOCK_CONFIRMATION",
            {
                'block_hash': block_hash
            },
            self.node_id
        )
        
        self.broadcast_message(message)
    
    def handle_block_confirmation(self, message: Message) -> None:
        """
        处理区块确认消息
        
        Args:
            message: 区块确认消息
        """
        block_hash = message.data['block_hash']
        
        # 确认区块
        self.blockchain.confirm_block(block_hash)
        
        # 如果区块已在本地链中，转发确认
        if any(block.hash == block_hash for block in self.blockchain.chain):
            # 转发给其他节点（除了发送者）
            for peer_id in self.peers:
                if peer_id != message.sender:
                    self.send_message_to_peer(peer_id, message)
    
    def sync_time(self) -> None:
        """同步网络时间"""
        if not self.peers:
            return
        
        # 请求时间样本
        for peer_id in self.peers:
            self.request_time_sample(peer_id)
        
        # 计算时间偏移量
        if self.time_samples:
            # 移除异常值
            sorted_samples = sorted(self.time_samples)
            if len(sorted_samples) > 4:
                # 移除最高和最低的25%
                quarter = len(sorted_samples) // 4
                valid_samples = sorted_samples[quarter:-quarter]
            else:
                valid_samples = sorted_samples
            
            # 计算平均偏移量
            if valid_samples:
                avg_offset = sum(valid_samples) / len(valid_samples)
                self.time_offset = avg_offset
                print(f"时间同步完成，偏移量: {self.time_offset:.2f}秒")
        
        # 清空样本
        self.time_samples = []
        
        # 设置下一次同步
        threading.Timer(300, self.sync_time).start()
    
    def request_time_sample(self, peer_id: str) -> None:
        """
        请求时间样本
        
        Args:
            peer_id: 对等节点ID
        """
        local_time = time.time()
        
        request_message = Message(
            "TIME_SYNC_REQUEST",
            {
                'local_time': local_time
            },
            self.node_id
        )
        
        response = self.send_message_to_peer(peer_id, request_message)
        
        if response and response.type == "TIME_SYNC_RESPONSE":
            remote_time = response.data['remote_time']
            response_time = time.time()
            
            # 计算往返时间
            rtt = response_time - local_time
            
            # 计算偏移量（考虑往返时间的一半作为网络延迟）
            offset = remote_time - (local_time + rtt / 2)
            
            # 添加样本
            self.time_samples.append(offset)
            
            # 限制样本数量
            if len(self.time_samples) > self.max_time_samples:
                self.time_samples.pop(0)
    
    def handle_time_sync_request(self, message: Message) -> str:
        """
        处理时间同步请求
        
        Args:
            message: 时间同步请求消息
            
        Returns:
            str: 响应消息的JSON字符串
        """
        response_message = Message(
            "TIME_SYNC_RESPONSE",
            {
                'remote_time': time.time()
            },
            self.node_id
        )
        
        return response_message.to_json()
    
    def get_network_time(self) -> float:
        """
        获取网络同步时间
        
        Returns:
            float: 网络同步时间
        """
        return time.time() + self.time_offset
