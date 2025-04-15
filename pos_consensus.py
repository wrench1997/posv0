# pos_consensus.py

import random
import time
from typing import Dict, List, Tuple, Optional
import hashlib

from blockchain_core import Blockchain, Block, Transaction

class StakeInfo:
    """质押信息类"""
    
    def __init__(self, address: str, amount: float, timestamp: float):
        """
        初始化质押信息
        
        Args:
            address: 质押者地址
            amount: 质押金额
            timestamp: 质押时间戳
        """
        self.address = address
        self.amount = amount
        self.timestamp = timestamp
        self.age = 0  # 质押年龄，用于计算权重
    
    def update_age(self, current_time: float) -> None:
        """
        更新质押年龄
        
        Args:
            current_time: 当前时间戳
        """
        # 质押年龄以天为单位
        self.age = (current_time - self.timestamp) / (24 * 60 * 60)
    
    def get_weight(self) -> float:
        """
        获取质押权重
        
        Returns:
            float: 质押权重
        """
        # 权重 = 质押金额 * 质押年龄（最大为90天）
        return self.amount * min(self.age, 90)


class POSConsensus:
    """POS共识机制类"""
    
    def __init__(self, blockchain: Blockchain, min_stake_amount: float = 10.0):
        """
        初始化POS共识机制
        
        Args:
            blockchain: 区块链实例
            min_stake_amount: 最小质押金额
        """
        self.blockchain = blockchain
        self.min_stake_amount = min_stake_amount
        self.stakes: Dict[str, StakeInfo] = {}  # 地址 -> 质押信息
        self.validators: List[str] = []  # 验证者地址列表
        self.last_block_time = time.time()
        self.block_time = 30  # 区块生成时间间隔（秒）
    
    def add_stake(self, address: str, amount: float) -> bool:
        """
        添加质押
        
        Args:
            address: 质押者地址
            amount: 质押金额
            
        Returns:
            bool: 质押是否成功
        """
        if amount < self.min_stake_amount:
            print(f"质押金额 {amount} 小于最小质押金额 {self.min_stake_amount}")
            return False
        
        current_time = time.time()
        
        if address in self.stakes:
            # 增加现有质押
            self.stakes[address].amount += amount
            print(f"地址 {address} 增加质押 {amount}，总质押: {self.stakes[address].amount}")
        else:
            # 添加新质押
            self.stakes[address] = StakeInfo(address, amount, current_time)
            print(f"地址 {address} 添加新质押 {amount}")
        
        # 如果质押金额达到最小质押金额，将地址添加到验证者列表
        if address not in self.validators and self.stakes[address].amount >= self.min_stake_amount:
            self.validators.append(address)
            print(f"地址 {address} 成为验证者")
        
        return True
    
    def remove_stake(self, address: str, amount: float) -> bool:
        """
        移除质押
        
        Args:
            address: 质押者地址
            amount: 要移除的质押金额
            
        Returns:
            bool: 移除质押是否成功
        """
        if address not in self.stakes:
            print(f"地址 {address} 没有质押")
            return False
        
        if amount > self.stakes[address].amount:
            print(f"移除质押金额 {amount} 大于当前质押金额 {self.stakes[address].amount}")
            return False
        
        # 减少质押金额
        self.stakes[address].amount -= amount
        print(f"地址 {address} 移除质押 {amount}，剩余质押: {self.stakes[address].amount}")
        
        # 如果质押金额低于最小质押金额，将地址从验证者列表中移除
        if self.stakes[address].amount < self.min_stake_amount and address in self.validators:
            self.validators.remove(address)
            print(f"地址 {address} 不再是验证者")
        
        # 如果质押金额为0，移除质押信息
        if self.stakes[address].amount == 0:
            del self.stakes[address]
            print(f"地址 {address} 的质押已完全移除")
        
        return True
    
    def select_validator(self) -> Optional[str]:
        """选择验证者生成下一个区块"""
        if not self.validators:
            print("没有验证者可供选择")
            return None
        
        current_time = time.time()
        
        # 更新所有质押的年龄
        for stake in self.stakes.values():
            stake.update_age(current_time)

        # 使用更精确的时间窗口和区块高度
        latest_block = self.blockchain.get_latest_block()
        block_height = latest_block.index
        time_window = int(current_time / self.block_time)
        
        # 使用区块链当前状态、时间窗口、区块高度和交易池大小作为随机种子
        seed_data = f"{latest_block.hash}_{time_window}_{block_height}_{len(self.blockchain.pending_transactions)}"
        seed = int(hashlib.sha256(seed_data.encode()).hexdigest(), 16)
        random.seed(seed)
        
        # 计算总权重
        total_weight = sum(self.stakes[v].get_weight() for v in self.validators)
        
        if total_weight == 0:
            # 如果总权重为0，使用确定性随机选择
            validator_index = seed % len(self.validators)
            return self.validators[validator_index]
        
        # 根据权重选择验证者
        target = random.uniform(0, total_weight)
        current_weight = 0
        
        for validator in self.validators:
            current_weight += self.stakes[validator].get_weight()
            if current_weight >= target:
                return validator
        
        # 如果没有选中验证者（理论上不应该发生），返回第一个验证者
        return self.validators[0]
    
    def is_time_to_forge(self) -> bool:
        """
        检查是否到了生成新区块的时间
        
        Returns:
            bool: 是否到了生成新区块的时间
        """
        current_time = time.time()
        return current_time - self.last_block_time >= self.block_time
    
    def forge_block(self, validator_address: str) -> Optional[Block]:
        """
        生成新区块
        
        Args:
            validator_address: 验证者地址
            
        Returns:
            Optional[Block]: 生成的新区块，如果生成失败则返回None
        """
        if validator_address not in self.validators:
            print(f"地址 {validator_address} 不是验证者")
            return None
        
        # 创建新区块
        new_block = self.blockchain.create_block(validator_address)
        
        # 更新最后区块时间
        self.last_block_time = time.time()
        
        print(f"验证者 {validator_address} 生成新区块: {new_block.index}")
        
        return new_block
    
    def validate_block(self, block: Block) -> bool:
        """
        验证区块是否由有效的验证者生成
        
        Args:
            block: 要验证的区块
            
        Returns:
            bool: 区块是否有效
        """
        if block.validator not in self.validators:
            print(f"区块验证者 {block.validator} 不是有效的验证者")
            return False
        
        # 验证区块哈希
        if block.hash != block.calculate_hash():
            print(f"区块哈希无效: {block.hash} != {block.calculate_hash()}")
            return False
        
        return True
    
    def get_validator_info(self) -> List[Dict]:
        """
        获取所有验证者的信息
        
        Returns:
            List[Dict]: 验证者信息列表
        """
        current_time = time.time()
        
        # 更新所有质押的年龄
        for stake in self.stakes.values():
            stake.update_age(current_time)
        
        validator_info = []
        
        for validator in self.validators:
            stake = self.stakes[validator]
            validator_info.append({
                'address': validator,
                'stake_amount': stake.amount,
                'stake_age': stake.age,
                'weight': stake.get_weight()
            })
        
        return validator_info



    def reset_block_generation(self) -> None:
        """重置区块生成计时器"""
        self.last_block_time = time.time()
        print("重置区块生成计时器")