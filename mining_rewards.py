# mining_rewards.py

from typing import Dict, List, Optional
import time

from blockchain_core import Blockchain, Block, Transaction

class RewardCalculator:
    """奖励计算器类"""
    
    def __init__(self, base_reward: float = 50.0, halving_interval: int = 210000):
        """
        初始化奖励计算器
        
        Args:
            base_reward: 基础区块奖励
            halving_interval: 奖励减半间隔（区块数）
        """
        self.base_reward = base_reward
        self.halving_interval = halving_interval
    
    def calculate_block_reward(self, block_index: int) -> float:
        """
        计算区块奖励
        
        Args:
            block_index: 区块索引
            
            
        Returns:
            float: 区块奖励金额
        """
        # 计算减半次数
        halvings = block_index // self.halving_interval
        
        # 计算奖励（每次减半奖励减少一半）
        reward = self.base_reward / (2 ** halvings)
        
        # 如果奖励小于0.00000001，则设为0
        if reward < 0.00000001:
            reward = 0
        
        return reward
    
    def calculate_transaction_fees(self, transactions: List[Transaction]) -> float:
        """
        计算交易费用总和
        
        Args:
            transactions: 交易列表
            
        Returns:
            float: 交易费用总和
        """
        return sum(tx.fee for tx in transactions)
    
    def calculate_total_reward(self, block: Block) -> float:
        """
        计算区块总奖励（区块奖励 + 交易费用）
        
        Args:
            block: 区块
            
        Returns:
            float: 区块总奖励
        """
        block_reward = self.calculate_block_reward(block.index)
        transaction_fees = self.calculate_transaction_fees(block.transactions)
        
        return block_reward + transaction_fees


class RewardDistributor:
    """奖励分配器类"""
    
    def __init__(self, blockchain: Blockchain, reward_calculator: RewardCalculator):
        """
        初始化奖励分配器
        
        Args:
            blockchain: 区块链实例
            reward_calculator: 奖励计算器实例
        """
        self.blockchain = blockchain
        self.reward_calculator = reward_calculator
    
    def distribute_reward(self, block: Block) -> Transaction:
        """
        分配区块奖励
        
        Args:
            block: 区块
            
        Returns:
            Transaction: 奖励交易
        """
        # 计算总奖励
        total_reward = self.reward_calculator.calculate_total_reward(block)
        
        # 创建奖励交易
        reward_transaction = Transaction(
            sender="COINBASE",
            recipient=block.validator,
            amount=total_reward,
            fee=0  # 奖励交易没有手续费
        )
        
        # 设置交易ID和签名
        reward_transaction.transaction_id = f"REWARD_{block.index}_{int(time.time())}"
        reward_transaction.sign_transaction("SYSTEM")
        
        print(f"向验证者 {block.validator} 分配奖励: {total_reward}")
        
        return reward_transaction
    
    def add_reward_transaction(self, block: Block) -> None:
        """
        向区块添加奖励交易
        
        Args:
            block: 区块
        """
        reward_transaction = self.distribute_reward(block)
        
        # 将奖励交易添加到区块的交易列表中
        block.transactions.insert(0, reward_transaction)
        
        # 重新计算区块哈希
        block.hash = block.calculate_hash()
        
        print(f"向区块 {block.index} 添加奖励交易: {reward_transaction.transaction_id}")
