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
    
    # 在 POSConsensus 类的 __init__ 方法中修改
    def __init__(self, blockchain: Blockchain, min_stake_amount: float = 10.0):
        """
        初始化POS共识机制
        
        Args:
            blockchain: 区块链实
            例
            min_stake_amount: 最小质押金额
        """
        self.blockchain = blockchain
        self.min_stake_amount = min_stake_amount
        self.stakes: Dict[str, StakeInfo] = {}  # 地址 -> 质押信息
        self.validators: List[str] = []  # 验证者地址列表
        self.last_block_time = time.time()
        self.block_time = 10  # 区块生成时间间隔（秒），从30秒改为180秒（3分钟）
    
    # 在 pos_consensus.py 文件中修改 add_stake 方法

    def add_stake(self, address: str, amount: float, is_initial_node: bool = False) -> bool:
        """
        添加质押
        
        Args:
            address: 质押者地址
            amount: 质押金额
            is_initial_node: 是否为初始节点（初始节点可以绕过最小质押金额限制）
            
        Returns:
            bool: 质押是否成功
        """
        # 允许任何节点进行质押，但没有资金的节点将排在最后
        # 如果不是初始节点，检查最小质押金额
        if not is_initial_node and amount < self.min_stake_amount:
            print(f"质押金额 {amount} 小于最小质押金额 {self.min_stake_amount}，但仍允许质押")
            # 继续执行，不返回 False
        
        current_time = time.time()
        
        if address in self.stakes:
            # 增加现有质押
            self.stakes[address].amount += amount
            print(f"地址 {address} 增加质押 {amount}，总质押: {self.stakes[address].amount}")
        else:
            # 添加新质押
            self.stakes[address] = StakeInfo(address, amount, current_time)
            print(f"地址 {address} 添加新质押 {amount}")
        
        # 将地址添加到验证者列表，无论质押金额多少
        if address not in self.validators:
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
        if validator_address not in self.validators:
            print(f"地址 {validator_address} 不是验证者")
            return None
        
        # 创建新区块
        new_block = self.blockchain.create_block(validator_address)
        
        # 确保区块索引正确
        expected_index = len(self.blockchain.chain)
        if new_block.index != expected_index:
            print(f"区块索引不匹配，期望 {expected_index}，实际 {new_block.index}，重新设置索引")
            new_block.index = expected_index
            new_block.previous_hash = self.blockchain.get_latest_block().hash
            new_block.hash = new_block.calculate_hash()
        
        # 更新最后区块时间
        self.last_block_time = time.time()
        
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




# 在pos_consensus.py文件中添加Tendermint相关类和方法

class TendermintConsensus:
    """Tendermint共识机制实现"""
    
    # 区块状态
    STATE_PRE_PREPARE = "PRE_PREPARE"
    STATE_PREPARE = "PREPARE"
    STATE_COMMIT = "COMMIT"
    STATE_FINALIZED = "FINALIZED"
    
    def __init__(self, blockchain, pos_consensus):
        """
        初始化Tendermint共识
        
        Args:
            blockchain: 区块链实例
            pos_consensus: POS共识实例，用于验证者选择
        """
        self.blockchain = blockchain
        self.pos_consensus = pos_consensus
        self.current_height = len(blockchain.chain)
        self.current_round = 0
        self.current_step = self.STATE_PRE_PREPARE
        
        # 存储投票
        self.prepare_votes = {}  # {validator: vote}
        self.commit_votes = {}   # {validator: vote}
        
        # 当前提议的区块
        self.proposed_block = None
        self.proposer = None
        
        # 超时设置
        self.propose_timeout = 30  # 秒
        self.prepare_timeout = 5   # 秒
        self.commit_timeout = 5    # 秒
        
        # 最后活动时间
        self.last_activity_time = time.time()
    
    def reset_for_new_height(self):
        """为新的区块高度重置状态"""
        self.current_height = len(self.blockchain.chain)
        self.current_round = 0
        self.current_step = self.STATE_PRE_PREPARE
        self.prepare_votes = {}
        self.commit_votes = {}
        self.proposed_block = None
        self.proposer = None
        self.last_activity_time = time.time()
    
    # 在TendermintConsensus的start_new_round方法中
    def start_new_round(self):
        self.current_round += 1
        self.current_step = self.STATE_PRE_PREPARE
        self.prepare_votes = {}
        self.commit_votes = {}
        self.proposed_block = None
        self.last_activity_time = time.time()
        
        # 选择提议者
        self.proposer = self.select_proposer()
        
        print(f"开始新轮次: 高度={self.current_height}, 轮次={self.current_round}, 提议者={self.proposer}")
        print(f"当前验证者列表: {self.pos_consensus.validators}")
        print(f"当前质押信息: {self.pos_consensus.stakes}")
        
    def select_proposer(self):
        """选择区块提议者"""
        # 使用轮次作为随机种子
        seed = f"{self.current_height}_{self.current_round}"
        seed_hash = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
        
        # 获取验证者列表
        validators = self.pos_consensus.validators
        if not validators:
            print("错误：没有可用的验证者")
            return None
        
        # 打印验证者信息，帮助调试
        print(f"当前验证者列表: {validators}")
        
        # 根据权重选择提议者
        weights = []
        for v in validators:
            if v in self.pos_consensus.stakes:
                weight = self.pos_consensus.stakes[v].get_weight()
                weights.append(weight)
                print(f"验证者 {v} 权重: {weight}")
            else:
                weights.append(0)
                print(f"验证者 {v} 未找到质押信息，权重设为0")
        
        total_weight = sum(weights)
        
        if total_weight == 0:
            # 如果总权重为0，使用确定性随机选择
            selected_index = seed_hash % len(validators)
            print(f"总权重为0，使用随机选择: 索引 {selected_index}")
            return validators[selected_index]
        
        # 使用加权随机选择
        r = (seed_hash / (2**256)) * total_weight
        cumulative_weight = 0
        
        for i, weight in enumerate(weights):
            cumulative_weight += weight
            if cumulative_weight > r:
                print(f"选择验证者 {validators[i]}，累积权重 {cumulative_weight} > {r}")
                return validators[i]
        
        # 如果没有选中（理论上不应该发生），返回第一个验证者
        print(f"未选中验证者，返回第一个: {validators[0]}")
        return validators[0]
    
    def propose_block(self, validator_address):
        """
        提议新区块
        
        Args:
            validator_address: 验证者地址
            
        Returns:
            Block: 提议的区块，如果不是提议者则返回None
        """
        # 检查是否是当前提议者
        if validator_address != self.proposer:
            print(f"节点 {validator_address} 不是当前提议者 {self.proposer}")
            return None
        
        # 创建新区块
        new_block = self.blockchain.create_block(validator_address)
        
        # 设置提议的区块
        self.proposed_block = new_block
        self.current_step = self.STATE_PREPARE
        self.last_activity_time = time.time()
        
        print(f"节点 {validator_address} 提议新区块: {new_block.index}")
        
        return new_block
    
    def prepare_vote(self, validator_address, block_hash, signature):
        """
        准备阶段投票
        
        Args:
            validator_address: 验证者地址
            block_hash: 区块哈希
            signature: 投票签名
            
        Returns:
            bool: 投票是否有效
        """
        # 检查是否是有效验证者
        if validator_address not in self.pos_consensus.validators:
            print(f"准备投票: {validator_address} 不是有效验证者")
            return False
        
        # 检查是否在准备阶段
        if self.current_step != self.STATE_PREPARE:
            # print(f"准备投票: 当前不在准备阶段，当前阶段: {self.current_step}")
            return False
        
        # 检查区块哈希是否匹配
        if not self.proposed_block or block_hash != self.proposed_block.hash:
            print(f"准备投票: 区块哈希不匹配")
            return False
        
        # 添加投票
        self.prepare_votes[validator_address] = {
            'block_hash': block_hash,
            'signature': signature
        }
        
        print(f"节点 {validator_address} 提交准备投票，当前准备投票数: {len(self.prepare_votes)}")
        
        # 检查是否达到准备阶段的阈值（2/3验证者）
        if self.check_prepare_quorum():
            self.current_step = self.STATE_COMMIT
            self.last_activity_time = time.time()
            print(f"达到准备阶段阈值，进入提交阶段")
            return True
        
        return True
    
    def commit_vote(self, validator_address, block_hash, signature):
        """
        提交阶段投票
        
        Args:
            validator_address: 验证者地址
            block_hash: 区块哈希
            signature: 投票签名
            
        Returns:
            bool: 投票是否有效
        """
        # 检查是否是有效验证者
        if validator_address not in self.pos_consensus.validators:
            print(f"提交投票: {validator_address} 不是有效验证者")
            return False
        
        # 检查是否在提交阶段
        if self.current_step != self.STATE_COMMIT:
            #print(f"提交投票: 当前不在提交阶段，当前阶段: {self.current_step}")
            return False
        
        # 检查区块哈希是否匹配
        if not self.proposed_block or block_hash != self.proposed_block.hash:
            print(f"提交投票: 区块哈希不匹配")
            return False
        
        # 添加投票
        self.commit_votes[validator_address] = {
            'block_hash': block_hash,
            'signature': signature
        }
        
        print(f"节点 {validator_address} 提交提交投票，当前提交投票数: {len(self.commit_votes)}")
        
        # 检查是否达到提交阶段的阈值（2/3验证者）
        if self.check_commit_quorum():
            self.finalize_block()
            return True
        
        return True
    
    def check_prepare_quorum(self):
        """检查是否达到准备阶段的法定人数"""
        # 单节点环境下，只需要自己的投票
        if len(self.pos_consensus.validators) <= 1:
            return len(self.prepare_votes) > 0
        
        # 多节点环境下，需要2/3的投票
        total_validators = len(self.pos_consensus.validators)
        required_votes = (total_validators * 2) // 3 + 1
        return len(self.prepare_votes) >= required_votes

    
    def check_commit_quorum(self):
        """检查是否达到提交阶段的法定人数"""
        # 单节点环境下，只需要自己的投票
        if len(self.pos_consensus.validators) <= 1:
            return len(self.commit_votes) > 0
        
        # 多节点环境下，需要2/3的投票
        total_validators = len(self.pos_consensus.validators)
        required_votes = (total_validators * 2) // 3 + 1
        return len(self.commit_votes) >= required_votes
    
    def finalize_block(self):
        """最终确认区块并添加到区块链"""
        if not self.proposed_block:
            print("没有提议的区块可以最终确认")
            return False
        
        # 添加区块到区块链
        if self.blockchain.add_block(self.proposed_block):
            self.current_step = self.STATE_FINALIZED
            print(f"区块 {self.proposed_block.index} 已最终确认并添加到区块链")
            
            # 将区块标记为已最终确认
            self.blockchain.finalized_blocks.add(self.proposed_block.hash)
            
            # 重置状态，准备下一个高度
            self.reset_for_new_height()
            
            return True
        else:
            print(f"添加区块 {self.proposed_block.index} 到区块链失败")
            
            # 开始新的轮次
            self.start_new_round()
            
            return False
        
    def check_timeout(self):
        """
        检查当前阶段是否超时
        
        Returns:
            bool: 是否超时
        """
        current_time = time.time()
        elapsed_time = current_time - self.last_activity_time
        
        if self.current_step == self.STATE_PRE_PREPARE:
            return elapsed_time > self.propose_timeout
        elif self.current_step == self.STATE_PREPARE:
            return elapsed_time > self.prepare_timeout
        elif self.current_step == self.STATE_COMMIT:
            return elapsed_time > self.commit_timeout
        
        return False
    
    def handle_timeout(self):
        """处理超时情况"""
        print(f"阶段 {self.current_step} 超时，开始新的轮次")
        self.start_new_round()
    
    def is_validator(self, address):
        """
        检查地址是否是验证者
        
        Args:
            address: 要检查的地址
            
        Returns:
            bool: 是否是验证者
        """
        return address in self.pos_consensus.validators