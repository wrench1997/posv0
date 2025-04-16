
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


class NodeDiscovery:
    """节点发现类，实现类似以太坊的节点发现机制"""
    
    def __init__(self, node_id: str, host: str, port: int, bootstrap_nodes=None):
        """
        初始化节点发现
        
        Args:
            node_id: 节点ID
            host: 主机地址
            port: 端口号
            bootstrap_nodes: 引导节点列表 [(host, port), ...]
        """
        self.node_id = node_id
        self.host = host
        self.port = port
        self.bootstrap_nodes = bootstrap_nodes or []
        
        # 节点表 - 类似Kademlia的k-bucket结构
        self.node_buckets = [[] for _ in range(256)]  # 256个桶
        self.max_bucket_size = 16  # 每个桶最多存储16个节点
        
        # 创建私钥用于签名
        self.private_key = ec.generate_private_key(ec.SECP256K1())
        self.public_key = self.private_key.public_key()
        
        # 计算节点ID (如果未提供)
        if not node_id:
            self.node_id = self._generate_node_id()
    
    def _generate_node_id(self) -> str:
        """从公钥生成节点ID"""
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.CompressedPoint
        )
        return hashlib.sha256(public_bytes).hexdigest()
    
    def _calculate_distance(self, node_id1: str, node_id2: str) -> int:
        """计算两个节点ID之间的XOR距离"""
        # 将十六进制字符串转换为整数
        int1 = int(node_id1, 16)
        int2 = int(node_id2, 16)
        # 计算XOR距离
        xor_result = int1 ^ int2
        # 返回最高位的位置 (类似于log2)
        if xor_result == 0:
            return 0
        return xor_result.bit_length() - 1
    
    def _get_bucket_index(self, node_id: str) -> int:
        """获取节点应该放入的桶索引"""
        return self._calculate_distance(self.node_id, node_id)
    
    def add_node(self, node_id: str, host: str, port: int) -> bool:
        """
        添加节点到路由表
        
        Args:
            node_id: 节点ID
            host: 主机地址
            port: 端口号
            
        Returns:
            bool: 是否成功添加
        """
        # 不添加自己
        if node_id == self.node_id:
            return False
        
        bucket_index = self._get_bucket_index(node_id)
        bucket = self.node_buckets[bucket_index]
        
        # 检查节点是否已存在
        for i, node in enumerate(bucket):
            if node['node_id'] == node_id:
                # 节点已存在，移动到列表末尾 (最近使用)
                bucket.append(bucket.pop(i))
                return True
        
        # 如果桶未满，直接添加
        if len(bucket) < self.max_bucket_size:
            bucket.append({
                'node_id': node_id,
                'host': host,
                'port': port,
                'last_seen': time.time()
            })
            return True
        
        # 桶已满，检查最早的节点是否仍然活跃
        oldest_node = bucket[0]
        if self.ping_node(oldest_node['host'], oldest_node['port']):
            # 最早的节点仍然活跃，移动到列表末尾
            bucket.append(bucket.pop(0))
            return False
        else:
            # 最早的节点不活跃，替换它
            bucket[0] = {
                'node_id': node_id,
                'host': host,
                'port': port,
                'last_seen': time.time()
            }
            return True
    
    def find_node(self, target_id: str, alpha: int = 3) -> List[Dict[str, Any]]:
        """
        查找最接近目标ID的节点
        
        Args:
            target_id: 目标节点ID
            alpha: 并行查询数量
            
        Returns:
            List[Dict[str, Any]]: 找到的节点列表
        """
        # 初始化已查询和待查询节点集合
        queried_nodes = set()
        pending_nodes = []
        
        # 从所有桶中找出最接近目标的节点
        for bucket in self.node_buckets:
            for node in bucket:
                pending_nodes.append(node)
        
        # 按照与目标的距离排序
        pending_nodes.sort(key=lambda n: self._calculate_distance(n['node_id'], target_id))
        
        # 保留最接近的k个节点
        k = 20  # 类似于Kademlia的k参数
        closest_nodes = []
        
        # 迭代查找过程
        while pending_nodes and len(closest_nodes) < k:
            # 选择alpha个最近的未查询节点
            current_batch = []
            for _ in range(min(alpha, len(pending_nodes))):
                node = pending_nodes.pop(0)
                if node['node_id'] not in queried_nodes:
                    current_batch.append(node)
                    queried_nodes.add(node['node_id'])
            
            if not current_batch:
                break
            
            # 并行查询这些节点
            new_nodes = []
            for node in current_batch:
                # 向节点发送FIND_NODE请求
                found_nodes = self.send_find_node_request(
                    node['host'], 
                    node['port'], 
                    target_id
                )
                
                # 更新节点的最后见到时间
                node['last_seen'] = time.time()
                
                # 添加到最接近的节点列表
                closest_nodes.append(node)
                
                # 处理返回的节点
                for found_node in found_nodes:
                    if found_node['node_id'] not in queried_nodes:
                        new_nodes.append(found_node)
            
            # 将新发现的节点添加到待查询列表
            for node in new_nodes:
                pending_nodes.append(node)
            
            # 重新排序
            pending_nodes.sort(key=lambda n: self._calculate_distance(n['node_id'], target_id))
        
        # 返回最接近的k个节点
        return closest_nodes[:k]
    
    def ping_node(self, host: str, port: int) -> bool:
        """
        Ping节点检查是否活跃
        
        Args:
            host: 主机地址
            port: 端口号
            
        Returns:
            bool: 节点是否活跃
        """
        try:
            # 创建客户端套接字
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(2)  # 设置超时时间
            client_socket.connect((host, port))
            
            # 创建PING消息
            ping_message = {
                'type': 'PING',
                'from': {
                    'node_id': self.node_id,
                    'host': self.host,
                    'port': self.port
                },
                'timestamp': time.time()
            }
            
            # 签名消息
            message_bytes = json.dumps(ping_message).encode()
            signature = self.private_key.sign(
                message_bytes,
                ec.ECDSA(hashes.SHA256())
            )
            
            # 添加签名
            ping_message['signature'] = base64.b64encode(signature).decode('utf-8')
            
            # 发送消息
            client_socket.send(json.dumps(ping_message).encode('utf-8'))
            
            # 接收响应
            response = client_socket.recv(4096).decode('utf-8')
            response_data = json.loads(response)
            
            # 验证响应类型
            if response_data['type'] == 'PONG':
                return True
            
            return False
        except Exception as e:
            print(f"Ping节点 {host}:{port} 失败: {e}")
            return False
        finally:
            client_socket.close()
    
    def send_find_node_request(self, host: str, port: int, target_id: str) -> List[Dict[str, Any]]:
        """
        发送FIND_NODE请求
        
        Args:
            host: 主机地址
            port: 端口号
            target_id: 目标节点ID
            
        Returns:
            List[Dict[str, Any]]: 找到的节点列表
        """
        try:
            # 创建客户端套接字
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5)  # 设置超时时间
            client_socket.connect((host, port))
            
            # 创建FIND_NODE消息
            find_node_message = {
                'type': 'FIND_NODE',
                'from': {
                    'node_id': self.node_id,
                    'host': self.host,
                    'port': self.port
                },
                'target': target_id,
                'timestamp': time.time()
            }
            
            # 签名消息
            message_bytes = json.dumps(find_node_message).encode()
            signature = self.private_key.sign(
                message_bytes,
                ec.ECDSA(hashes.SHA256())
            )
            
            # 添加签名
            find_node_message['signature'] = base64.b64encode(signature).decode('utf-8')
            
            # 发送消息
            client_socket.send(json.dumps(find_node_message).encode('utf-8'))
            
            # 接收响应
            response = client_socket.recv(4096).decode('utf-8')
            response_data = json.loads(response)
            
            # 验证响应类型
            if response_data['type'] == 'NEIGHBORS':
                return response_data['nodes']
            
            return []
        except Exception as e:
            print(f"发送FIND_NODE请求到 {host}:{port} 失败: {e}")
            return []
        finally:
            client_socket.close()
    
    def bootstrap(self) -> None:
        """从引导节点开始发现网络中的其他节点"""
        if not self.bootstrap_nodes:
            print("没有配置引导节点")
            return
        
        for host, port in self.bootstrap_nodes:
            try:
                # 创建客户端套接字
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(5)  # 设置超时时间
                client_socket.connect((host, port))
                
                # 创建PING消息
                ping_message = {
                    'type': 'PING',
                    'from': {
                        'node_id': self.node_id,
                        'host': self.host,
                        'port': self.port
                    },
                    'timestamp': time.time()
                }
                
                # 签名消息
                message_bytes = json.dumps(ping_message).encode()
                signature = self.private_key.sign(
                    message_bytes,
                    ec.ECDSA(hashes.SHA256())
                )
                
                # 添加签名
                ping_message['signature'] = base64.b64encode(signature).decode('utf-8')
                
                # 发送消息
                client_socket.send(json.dumps(ping_message).encode('utf-8'))
                
                # 接收响应
                response = client_socket.recv(4096).decode('utf-8')
                response_data = json.loads(response)
                
                # 验证响应类型
                if response_data['type'] == 'PONG':
                    # 添加引导节点
                    self.add_node(
                        response_data['from']['node_id'],
                        response_data['from']['host'],
                        response_data['from']['port']
                    )
                    
                    # 查找自己的节点ID，获取更多节点
                    self.find_node(self.node_id)
                    
                    print(f"成功连接到引导节点 {host}:{port}")
                
            except Exception as e:
                print(f"连接引导节点 {host}:{port} 失败: {e}")
            finally:
                client_socket.close()
    
    def start_discovery_server(self) -> None:
        """启动节点发现服务器"""
        # 创建服务器套接字
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(10)
        
        print(f"节点发现服务器启动，监听 {self.host}:{self.port}")
        
        # 启动处理连接的线程
        threading.Thread(target=self._handle_discovery_connections, args=(server_socket,), daemon=True).start()
    
    def _handle_discovery_connections(self, server_socket: socket.socket) -> None:
        """处理节点发现连接"""
        while True:
            try:
                client_socket, address = server_socket.accept()
                threading.Thread(target=self._handle_discovery_request, args=(client_socket,), daemon=True).start()
            except Exception as e:
                print(f"处理节点发现连接时出错: {e}")
    
    def _handle_discovery_request(self, client_socket: socket.socket) -> None:
        """处理节点发现请求"""
        try:
            # 接收请求
            data = client_socket.recv(4096)
            if not data:
                return
            
            request_data = json.loads(data.decode('utf-8'))
            request_type = request_data['type']
            
            # 验证签名
            signature = base64.b64decode(request_data['signature'])
            request_copy = request_data.copy()
            del request_copy['signature']
            
            # 处理不同类型的请求
            if request_type == 'PING':
                # 处理PING请求
                self._handle_ping_request(client_socket, request_data)
            elif request_type == 'FIND_NODE':
                # 处理FIND_NODE请求
                self._handle_find_node_request(client_socket, request_data)
            else:
                print(f"未知的请求类型: {request_type}")
        
        except Exception as e:
            print(f"处理节点发现请求时出错: {e}")
        finally:
            client_socket.close()
    
    def _handle_ping_request(self, client_socket: socket.socket, request_data: Dict[str, Any]) -> None:
        """处理PING请求"""
        # 添加发送方节点
        from_node = request_data['from']
        self.add_node(from_node['node_id'], from_node['host'], from_node['port'])
        
        # 创建PONG响应
        pong_message = {
            'type': 'PONG',
            'from': {
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port
            },
            'timestamp': time.time()
        }
        
        # 签名响应
        message_bytes = json.dumps(pong_message).encode()
        signature = self.private_key.sign(
            message_bytes,
            ec.ECDSA(hashes.SHA256())
        )
        
        # 添加签名
        pong_message['signature'] = base64.b64encode(signature).decode('utf-8')
        
        # 发送响应
        client_socket.send(json.dumps(pong_message).encode('utf-8'))
    
    def _handle_find_node_request(self, client_socket: socket.socket, request_data: Dict[str, Any]) -> None:
        """处理FIND_NODE请求"""
        # 添加发送方节点
        from_node = request_data['from']
        self.add_node(from_node['node_id'], from_node['host'], from_node['port'])
        
        # 获取目标ID
        target_id = request_data['target']
        
        # 查找最接近的节点
        closest_nodes = []
        for bucket in self.node_buckets:
            for node in bucket:
                closest_nodes.append(node)
        
        # 按照与目标的距离排序
        closest_nodes.sort(key=lambda n: self._calculate_distance(n['node_id'], target_id))
        
        # 取前k个节点
        k = 20
        closest_nodes = closest_nodes[:k]
        
        # 创建NEIGHBORS响应
        neighbors_message = {
            'type': 'NEIGHBORS',
            'from': {
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port
            },
            'nodes': closest_nodes,
            'timestamp': time.time()
        }
        
        # 签名响应
        message_bytes = json.dumps(neighbors_message).encode()
        signature = self.private_key.sign(
            message_bytes,
            ec.ECDSA(hashes.SHA256())
        )
        
        # 添加签名
        neighbors_message['signature'] = base64.b64encode(signature).decode('utf-8')
        
        # 发送响应
        client_socket.send(json.dumps(neighbors_message).encode('utf-8'))
    
    def refresh_buckets(self) -> None:
        """定期刷新所有桶"""
        # 对每个桶，查找一个随机ID
        for i in range(len(self.node_buckets)):
            # 生成一个随机ID，使其落在当前桶中
            random_id = self._generate_random_id_for_bucket(i)
            
            # 查找这个随机ID
            self.find_node(random_id)
    
    def _generate_random_id_for_bucket(self, bucket_index: int) -> str:
        """为指定桶生成一个随机ID"""
        # 复制自己的ID
        id_int = int(self.node_id, 16)
        
        # 翻转第bucket_index位
        mask = 1 << bucket_index
        id_int ^= mask
        
        # 随机化其他位
        for i in range(256):
            if i != bucket_index:
                # 50%的概率翻转每一位
                if random.random() < 0.5:
                    mask = 1 << i
                    id_int ^= mask
        
        # 转回十六进制字符串
        return hex(id_int)[2:].zfill(64)
    
    def start_refresh_timer(self) -> None:
        """启动定期刷新定时器"""
        # 每小时刷新一次所有桶
        self.refresh_buckets()
        threading.Timer(3600, self.start_refresh_timer).start()