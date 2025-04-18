# mining_rewards.py

from typing import Dict, List, Optional
import time
import math

from blockchain_core import Blockchain, Block, Transaction

class RewardCalculator:
    """奖励计算器类，实现动态奖励机制"""
    
    def __init__(self, 
                 initial_reward: float = 5.0,
                 max_supply: float = 21000000.0,
                 halving_blocks: int = 210000,
                 min_reward: float = 0.00000001):
        """
        初始化奖励计算器
        
        Args:
            initial_reward: 初始区块奖励
            max_supply: 最大代币供应量
            halving_blocks: 奖励减半间隔（区块数）
            min_reward: 最小奖励值
        """
        self.initial_reward = initial_reward
        self.max_supply = max_supply
        self.halving_blocks = halving_blocks
        self.min_reward = min_reward
        self.genesis_time = time.time()  # 创世区块时间
        
        # 缓存当前估计的供应量，避免重复计算
        self.last_supply_estimate = 0.0
        self.last_estimate_block = 0
        self.last_estimate_time = time.time()
    
    def calculate_block_reward(self, block_index: int, blockchain: Blockchain = None, 
                               pending_tx_count: int = 0) -> float:
        """
        计算区块奖励，考虑多种因素
        
        Args:
            block_index: 区块索引
            blockchain: 区块链实例，用于计算当前供应量和网络状态
            pending_tx_count: 待处理交易数量，用于评估网络拥堵程度
            
        Returns:
            float: 区块奖励金额
        """
        # 基础奖励（考虑减半）
        halvings = block_index // self.halving_blocks
        base_reward = self.initial_reward / (2 ** halvings)
        
        # 确保奖励不低于最小值
        if base_reward < self.min_reward:
            base_reward = self.min_reward
        
        # 如果没有提供区块链实例，返回基础奖励
        if not blockchain:
            return base_reward
        
        # 估计当前供应量
        current_supply = self.estimate_current_supply(blockchain, block_index)
        
        # 供应量调整因子（接近最大供应量时减少奖励）
        supply_factor = max(0.1, 1 - (current_supply / self.max_supply))
        
        # 网络拥堵调整因子
        congestion_factor = self.calculate_congestion_factor(pending_tx_count)
        
        # 时间调整因子（确保区块生成速度稳定）
        time_factor = self.calculate_time_factor(blockchain)
        
        # 计算最终奖励
        final_reward = base_reward * supply_factor * congestion_factor * time_factor
        
        # 确保不超过剩余可发行量
        remaining_supply = self.max_supply - current_supply
        if final_reward > remaining_supply:
            final_reward = remaining_supply
        
        # 确保奖励不低于最小值
        if final_reward < self.min_reward and remaining_supply > self.min_reward:
            final_reward = self.min_reward
        
        return final_reward
    
    def estimate_current_supply(self, blockchain: Blockchain, current_block: int) -> float:
        """
        估计当前代币供应量
        
        Args:
            blockchain: 区块链实例
            current_block: 当前区块索引
            
        Returns:
            float: 估计的当前供应量
        """
        # 如果区块索引没有变化太多，使用缓存值
        if (abs(current_block - self.last_estimate_block) < 10 and 
            time.time() - self.last_estimate_time < 300):  # 5分钟内
            return self.last_supply_estimate
        
        # 计算所有区块奖励和交易费用
        total_supply = 0.0
        
        # 遍历所有区块
        for block in blockchain.chain:
            # 查找coinbase交易（区块奖励）
            for tx in block.transactions:
                if tx.sender == "COINBASE":
                    total_supply += tx.amount
        
        # 更新缓存
        self.last_supply_estimate = total_supply
        self.last_estimate_block = current_block
        self.last_estimate_time = time.time()
        
        return total_supply
    
    def calculate_congestion_factor(self, pending_tx_count: int) -> float:
        """
        计算网络拥堵调整因子
        
        Args:
            pending_tx_count: 待处理交易数量
            
        Returns:
            float: 拥堵调整因子
        """
        # 基准交易数（认为是正常负载）
        base_tx_count = 100
        
        # 计算拥堵因子（使用sigmoid函数平滑过渡）
        congestion_ratio = pending_tx_count / base_tx_count
        congestion_factor = 1 + 0.5 * (2 / (1 + math.exp(-0.1 * (congestion_ratio - 5))) - 1)
        
        # 限制在合理范围内
        return max(0.8, min(congestion_factor, 2.0))
    
    def calculate_time_factor(self, blockchain: Blockchain) -> float:
        """
        计算时间调整因子，用于稳定区块生成速度
        
        Args:
            blockchain: 区块链实例
            
        Returns:
            float: 时间调整因子
        """
        # 如果区块链太短，返回默认值
        if len(blockchain.chain) < 10:
            return 1.0
        
        # 计算最近10个区块的平均生成时间
        recent_blocks = blockchain.chain[-10:]
        if len(recent_blocks) < 2:
            return 1.0
        
        time_diffs = []
        for i in range(1, len(recent_blocks)):
            time_diff = recent_blocks[i].timestamp - recent_blocks[i-1].timestamp
            if time_diff > 0:  # 避免时间戳错误
                time_diffs.append(time_diff)
        
        if not time_diffs:
            return 1.0
        
        avg_block_time = sum(time_diffs) / len(time_diffs)
        
        # 目标区块时间（秒）
        target_block_time = 10  # 3分钟
        
        # 计算时间因子（如果区块生成太快，减少奖励；太慢则增加奖励）
        time_factor = target_block_time / avg_block_time
        
        # 限制在合理范围内
        return max(0.5, min(time_factor, 2.0))
    
    def calculate_transaction_fees(self, transactions: List[Transaction]) -> float:
        """
        计算交易费用总和
        
        Args:
            transactions: 交易列表
            
        Returns:
            float: 交易费用总和
        """
        # 排除coinbase交易
        regular_txs = [tx for tx in transactions if tx.sender != "COINBASE"]
        return sum(tx.fee for tx in regular_txs)
    
    def calculate_total_reward(self, block: Block, blockchain: Blockchain = None) -> float:
        """
        计算区块总奖励（区块奖励 + 交易费用）
        
        Args:
            block: 区块
            blockchain: 区块链实例
            
        Returns:
            float: 区块总奖励
        """
        # 计算区块奖励
        pending_tx_count = len(blockchain.pending_transactions) if blockchain else 0
        block_reward = self.calculate_block_reward(block.index, blockchain, pending_tx_count)
        
        # 计算交易费用
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
        
        # 跟踪验证者的历史表现
        self.validator_performance = {}  # {validator_address: {blocks_validated: int, last_block_time: float}}
    
    def distribute_reward(self, block: Block) -> Transaction:
        """
        分配区块奖励
        
        Args:
            block: 区块
            
        Returns:
            Transaction: 奖励交易
        """
        # 更新验证者表现记录
        self.update_validator_performance(block)
        
        # 计算总奖励
        total_reward = self.reward_calculator.calculate_total_reward(block, self.blockchain)
        
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
    
    def update_validator_performance(self, block: Block) -> None:
        """
        更新验证者表现记录
        
        Args:
            block: 区块
        """
        validator = block.validator
        
        if validator not in self.validator_performance:
            self.validator_performance[validator] = {
                'blocks_validated': 0,
                'last_block_time': 0,
                'total_rewards': 0.0
            }
        
        # 更新验证者数据
        self.validator_performance[validator]['blocks_validated'] += 1
        self.validator_performance[validator]['last_block_time'] = block.timestamp
        
        # 计算并累加奖励
        reward = self.reward_calculator.calculate_total_reward(block, self.blockchain)
        self.validator_performance[validator]['total_rewards'] += reward
    
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
    
    def get_validator_statistics(self) -> Dict:
        """
        获取验证者统计信息
        
        Returns:
            Dict: 验证者统计信息
        """
        return self.validator_performance