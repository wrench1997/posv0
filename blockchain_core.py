
# blockchain_core.py

import hashlib
import json
import time
from typing import List, Dict, Any, Optional
import uuid

class Transaction:
    """交易类，表示区块链上的一笔交易"""
    
    def __init__(self, sender: str, recipient: str, amount: float, fee: float = 0.001):
        """
        初始化一笔交易
        
        Args:
            sender: 发送方地址
            recipient: 接收方地址
            amount: 交易金额
            fee: 交易费用
        """
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.fee = fee
        self.timestamp = time.time()
        self.transaction_id = str(uuid.uuid4())
        self.signature = None
        self.hash = self.calculate_hash()
        
    def calculate_hash(self) -> str:
        """计算交易的哈希值"""
        transaction_dict = {
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount,
            'fee': self.fee,
            'timestamp': self.timestamp,
            'transaction_id': self.transaction_id
        }
        transaction_string = json.dumps(transaction_dict, sort_keys=True)
        return hashlib.sha256(transaction_string.encode()).hexdigest()
    
    def sign_transaction(self, signature: str) -> None:
        """
        为交易添加签名并更新哈希值
        
        Args:
            signature: 交易签名
        """
        self.signature = signature
        # 更新哈希值
        self.hash = self.calculate_hash()
        
    def is_valid(self) -> bool:
        """验证交易是否有效"""
        # 在实际系统中，这里应该验证签名
        return self.signature is not None and self.hash == self.calculate_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        """将交易转换为字典格式"""
        return {
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount,
            'fee': self.fee,
            'timestamp': self.timestamp,
            'transaction_id': self.transaction_id,
            'signature': self.signature,
            'hash': self.hash
        }
    
    @classmethod
    def from_dict(cls, transaction_dict: Dict[str, Any]) -> 'Transaction':
        """从字典创建交易对象"""
        transaction = cls(
            sender=transaction_dict['sender'],
            recipient=transaction_dict['recipient'],
            amount=transaction_dict['amount'],
            fee=transaction_dict['fee']
        )
        transaction.timestamp = transaction_dict['timestamp']
        transaction.transaction_id = transaction_dict['transaction_id']
        transaction.signature = transaction_dict['signature']
        transaction.hash = transaction_dict['hash']
        return transaction


class Block:
    """区块类，表示区块链中的一个区块"""
    
    def __init__(self, index: int, timestamp: float, transactions: List[Transaction], 
                 previous_hash: str, validator: str = None):
        """
        初始化一个区块
        
        Args:
            index: 区块索引
            timestamp: 区块创建时间戳
            transactions: 区块包含的交易列表
            previous_hash: 前一个区块的哈希值
            validator: 验证者地址（在POS中是区块生成者）
        """
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.validator = validator
        self.nonce = 0
        self.hash = self.calculate_hash()
        
    def calculate_hash(self) -> str:
        """计算区块的哈希值"""
        # 将交易列表转换为可哈希的格式
        transactions_dict = [tx.to_dict() for tx in self.transactions]
        block_string = json.dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': transactions_dict,
            'previous_hash': self.previous_hash,
            'validator': self.validator,
            'nonce': self.nonce
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """将区块转换为字典格式"""
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'previous_hash': self.previous_hash,
            'validator': self.validator,
            'nonce': self.nonce,
            'hash': self.hash
        }
    
    @classmethod
    def from_dict(cls, block_dict: Dict[str, Any]) -> 'Block':
        """从字典创建区块对象"""
        transactions = [Transaction.from_dict(tx) for tx in block_dict['transactions']]
        block = cls(
            index=block_dict['index'],
            timestamp=block_dict['timestamp'],
            transactions=transactions,
            previous_hash=block_dict['previous_hash'],
            validator=block_dict['validator']
        )
        block.nonce = block_dict['nonce']
        block.hash = block_dict['hash']
        return block


class Blockchain:
    """区块链类，管理区块链的核心功能"""
    
    def __init__(self):
        """初始化区块链"""
        self.chain = []
        self.pending_transactions = []
        self.nodes = set()  # 存储网络中的节点
        self.block_confirmations = {}  # 存储区块确认数 {block_hash: confirmation_count}
        self.finalized_blocks = set()  # 存储已最终确认的区块哈希
        self.confirmation_threshold = 6  # 区块最终确认所需的确认数
        
        # 创建创世区块
        self.create_genesis_block()
        
    def create_genesis_block(self) -> None:
        """创建创世区块"""
        # 使用固定的时间戳而不是 time.time()
        fixed_timestamp = 1609459200.0  # 2021-01-01 00:00:00 UTC
        genesis_block = Block(0, fixed_timestamp, [], "0", "genesis")
        # 确保 nonce 也是固定的
        genesis_block.nonce = 0
        genesis_block.hash = genesis_block.calculate_hash()
        self.chain.append(genesis_block)
        
    def get_latest_block(self) -> Block:
        """获取最新的区块"""
        return self.chain[-1]
    
    def add_transaction(self, transaction: Transaction) -> bool:
        """
        添加交易到待处理交易池
        
        Args:
            transaction: 要添加的交易
            
        Returns:
            bool: 交易是否成功添加
        """
        if not transaction.is_valid():
            print(f"交易验证失败: {transaction.transaction_id}")
            return False
        
        self.pending_transactions.append(transaction)
        return True
    
    def create_block(self, validator: str) -> Block:
        """
        创建新区块
        
        Args:
            validator: 验证者地址
            
        Returns:
            Block: 新创建的区块
        """
        # 确保使用正确的索引
        current_index = len(self.chain)
        
        block = Block(
            index=current_index,
            timestamp=time.time(),
            transactions=self.pending_transactions.copy(),  # 使用副本避免引用问题
            previous_hash=self.get_latest_block().hash,
            validator=validator
        )
        
        # 清空待处理交易池
        self.pending_transactions = []
        
        return block
    
    def add_block(self, block: Block) -> bool:
        """
        将区块添加到区块链
        
        Args:
            block: 要添加的区块
            
        Returns:
            bool: 区块是否成功添加
        """
        # 验证区块
        if not self.is_valid_block(block):
            return False
        
        self.chain.append(block)
        return True
    
    def is_valid_block(self, block: Block) -> bool:
        """验证区块是否有效"""
        # 检查区块索引
        expected_index = len(self.chain)
        if block.index != expected_index:
            print(f"区块索引无效: {block.index} != {expected_index}")
            return False
        
        # 检查前一个区块的哈希值
        if block.previous_hash != self.get_latest_block().hash:
            print(f"前一个区块哈希值不匹配: {block.previous_hash} != {self.get_latest_block().hash}")
            return False
        
        # 检查区块哈希值
        if block.hash != block.calculate_hash():
            print(f"区块哈希值无效: {block.hash} != {block.calculate_hash()}")
            return False
        
        # 验证所有交易
        for transaction in block.transactions:
            if not transaction.is_valid():
                print(f"交易无效: {transaction.transaction_id}")
                return False
        
        return True  
    # def is_valid_block(self, block: Block) -> bool:
    #     """
    #     验证区块是否有效
        
    #     Args:
    #         block: 要验证的区块
            
    #     Returns:
    #         bool: 区块是否有效
    #     """
    #     # 检查区块索引
    #     expected_index = len(self.chain)
    #     if block.index != expected_index:
    #         print(f"区块索引无效: {block.index} != {expected_index}")
    #         return False
        
    #     # 检查前一个区块的哈希值
    #     if block.previous_hash != self.get_latest_block().hash:
    #         print(f"前一个区块哈希值不匹配: {block.previous_hash} != {self.get_latest_block().hash}")
    #         return False
        
    #     # 检查区块哈希值
    #     if block.hash != block.calculate_hash():
    #         print(f"区块哈希值无效: {block.hash} != {block.calculate_hash()}")
    #         return False
        
    #     # 验证所有交易
    #     for transaction in block.transactions:
    #         if not transaction.is_valid():
    #             print(f"交易无效: {transaction.transaction_id}")
    #             return False
        
    #     return True
    
    def is_chain_valid(self) -> bool:
        """
        验证整个区块链是否有效
        
        Returns:
            bool: 区块链是否有效
        """
        # 从第二个区块开始验证（跳过创世区块）
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            # 验证当前区块的哈希值
            if current_block.hash != current_block.calculate_hash():
                print(f"区块 {i} 哈希值无效")
                return False
            
            # 验证当前区块的前一个区块哈希值
            if current_block.previous_hash != previous_block.hash:
                print(f"区块 {i} 前一个区块哈希值不匹配")
                return False
        
        return True
    
    def confirm_block(self, block_hash: str) -> None:
        """确认区块"""
        # 检查区块是否存在于链中
        block_exists = False
        for block in self.chain:
            if block.hash == block_hash:
                block_exists = True
                break
        
        if not block_exists:
            return
        
        if block_hash not in self.block_confirmations:
            self.block_confirmations[block_hash] = 0
        
        self.block_confirmations[block_hash] += 1
        
        # 检查是否达到确认阈值
        if (self.block_confirmations[block_hash] >= self.confirmation_threshold and 
                block_hash not in self.finalized_blocks):
            self.finalized_blocks.add(block_hash)
            print(f"区块 {block_hash[:8]} 已最终确认")
    
    def is_block_finalized(self, block_hash: str) -> bool:
        """
        检查区块是否已最终确认
        
        Args:
            block_hash: 区块哈希
            
        Returns:
            bool: 区块是否已最终确认
        """
        return block_hash in self.finalized_blocks
    
    def to_dict(self) -> Dict[str, Any]:
        """将区块链转换为字典格式"""
        return {
            'chain': [block.to_dict() for block in self.chain],
            'pending_transactions': [tx.to_dict() for tx in self.pending_transactions]
        }
    
    @classmethod
    def from_dict(cls, blockchain_dict: Dict[str, Any]) -> 'Blockchain':
        """从字典创建区块链对象"""
        blockchain = cls()
        # 清空默认创建的创世区块
        blockchain.chain = []
        
        # 添加区块
        for block_dict in blockchain_dict['chain']:
            blockchain.chain.append(Block.from_dict(block_dict))
        
        # 添加待处理交易
        for tx_dict in blockchain_dict['pending_transactions']:
            blockchain.pending_transactions.append(Transaction.from_dict(tx_dict))
        
        return blockchain
