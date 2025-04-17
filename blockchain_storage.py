# blockchain_storage.py

import json
import os
from typing import Dict, Any, Optional
import time

from blockchain_core import Blockchain, Block, Transaction

class BlockchainStorage:
    """区块链数据存储类，负责区块链数据的持久化"""
    
    def __init__(self, data_dir: str = "blockchain_data"):
        """
        初始化区块链存储
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        
        # 创建数据目录
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(os.path.join(data_dir, "blocks"), exist_ok=True)
        os.makedirs(os.path.join(data_dir, "transactions"), exist_ok=True)
    
    def save_blockchain(self, blockchain: Blockchain, node_id: str) -> bool:
        """
        保存区块链数据
        
        Args:
            blockchain: 区块链实例
            node_id: 节点ID
            
        Returns:
            bool: 是否成功保存
        """
        try:
            # 保存区块链元数据
            metadata = {
                'chain_length': len(blockchain.chain),
                'last_update': time.time(),
                'node_id': node_id
            }
            
            metadata_path = os.path.join(self.data_dir, f"blockchain_metadata_{node_id}.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=4)
            
            # 保存每个区块
            for block in blockchain.chain:
                self.save_block(block, node_id)
            
            # 保存待处理交易
            pending_txs_path = os.path.join(self.data_dir, f"pending_transactions_{node_id}.json")
            with open(pending_txs_path, 'w') as f:
                json.dump([tx.to_dict() for tx in blockchain.pending_transactions], f, indent=4)
            
            print(f"区块链数据已保存，链长度: {len(blockchain.chain)}")
            return True
        except Exception as e:
            print(f"保存区块链数据失败: {e}")
            return False
    
    def save_block(self, block: Block, node_id: str) -> bool:
        """
        保存单个区块
        
        Args:
            block: 区块实例
            node_id: 节点ID
            
        Returns:
            bool: 是否成功保存
        """
        try:
            block_path = os.path.join(self.data_dir, "blocks", f"block_{block.index}_{node_id}.json")
            with open(block_path, 'w') as f:
                json.dump(block.to_dict(), f, indent=4)
            
            # 保存区块中的交易
            for tx in block.transactions:
                self.save_transaction(tx, node_id, block.index)
            
            return True
        except Exception as e:
            print(f"保存区块 {block.index} 失败: {e}")
            return False
    
    def save_transaction(self, transaction: Transaction, node_id: str, block_index: Optional[int] = None) -> bool:
        """
        保存交易
        
        Args:
            transaction: 交易实例
            node_id: 节点ID
            block_index: 区块索引（如果交易已包含在区块中）
            
        Returns:
            bool: 是否成功保存
        """
        try:
            tx_data = transaction.to_dict()
            if block_index is not None:
                tx_data['block_index'] = block_index
            
            tx_path = os.path.join(self.data_dir, "transactions", f"tx_{transaction.transaction_id}_{node_id}.json")
            with open(tx_path, 'w') as f:
                json.dump(tx_data, f, indent=4)
            
            return True
        except Exception as e:
            print(f"保存交易 {transaction.transaction_id} 失败: {e}")
            return False
    
    def load_blockchain(self, node_id: str) -> Optional[Blockchain]:
        """
        加载区块链数据
        
        Args:
            node_id: 节点ID
            
        Returns:
            Optional[Blockchain]: 加载的区块链实例，如果加载失败则返回None
        """
        metadata_path = os.path.join(self.data_dir, f"blockchain_metadata_{node_id}.json")
        
        if not os.path.exists(metadata_path):
            print(f"未找到节点 {node_id} 的区块链元数据")
            return None
        
        try:
            # 加载元数据
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            chain_length = metadata['chain_length']
            
            # 创建新的区块链实例
            blockchain = Blockchain()
            # 清空默认创建的创世区块
            blockchain.chain = []
            
            # 加载每个区块
            for i in range(chain_length):
                block_path = os.path.join(self.data_dir, "blocks", f"block_{i}_{node_id}.json")
                
                if not os.path.exists(block_path):
                    print(f"未找到区块 {i}，区块链数据可能已损坏")
                    return None
                
                with open(block_path, 'r') as f:
                    block_dict = json.load(f)
                
                block = Block.from_dict(block_dict)
                blockchain.chain.append(block)
            
            # 加载待处理交易
            pending_txs_path = os.path.join(self.data_dir, f"pending_transactions_{node_id}.json")
            if os.path.exists(pending_txs_path):
                with open(pending_txs_path, 'r') as f:
                    pending_txs_dict = json.load(f)
                
                blockchain.pending_transactions = [Transaction.from_dict(tx_dict) for tx_dict in pending_txs_dict]
            
            print(f"已加载区块链数据，链长度: {len(blockchain.chain)}")
            return blockchain
        except Exception as e:
            print(f"加载区块链数据失败: {e}")
            return None
    
    def get_transaction_history(self, address: str, node_id: str) -> list:
        """
        获取地址的交易历史
        
        Args:
            address: 钱包地址
            node_id: 节点ID
            
        Returns:
            list: 交易历史列表
        """
        tx_history = []
        tx_dir = os.path.join(self.data_dir, "transactions")
        
        if not os.path.exists(tx_dir):
            return []
        
        try:
            # 遍历所有交易文件
            for filename in os.listdir(tx_dir):
                if not filename.endswith(f"_{node_id}.json"):
                    continue
                
                tx_path = os.path.join(tx_dir, filename)
                
                with open(tx_path, 'r') as f:
                    tx_data = json.load(f)
                
                # 检查交易是否与地址相关
                if tx_data['sender'] == address or tx_data['recipient'] == address:
                    tx_history.append(tx_data)
            
            # 按时间戳排序
            tx_history.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return tx_history
        except Exception as e:
            print(f"获取交易历史失败: {e}")
            return []