# tendermint_consensus.py

import time
import random
import hashlib
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum

from blockchain_core import Blockchain, Block, Transaction

class ConsensusState(Enum):
    """共识状态枚举"""
    NEW_HEIGHT = 0  # 新的区块高度
    PROPOSE = 1     # 提议阶段
    PREVOTE = 2     # 预投票阶段
    PRECOMMIT = 3   # 预提交阶段
    COMMIT = 4      # 提交阶段

class Vote:
    """投票类"""
    
    def __init__(self, validator: str, block_hash: str, height: int, round_num: int, vote_type: str):
        """
        初始化投票
        
        Args:
            validator: 验证者地址
            block_hash: 区块哈希
            height: 区块高度
            round_num: 轮次
            vote_type: 投票类型 (prevote/precommit)
        """
        self.validator = validator
        self.block_hash = block_hash
        self.height = height
        self.round = round_num
        self.type = vote_type
        self.timestamp = time.time()
        self.signature = self.sign()
    
    def sign(self) -> str:
        """签名投票"""
        vote_data = f"{self.validator}_{self.block_hash}_{self.height}_{self.round}_{self.type}_{self.timestamp}"
        return hashlib.sha256(vote_data.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'validator': self.validator,
            'block_hash': self.block_hash,
            'height': self.height,
            'round': self.round,
            'type': self.type,
            'timestamp': self.timestamp,
            'signature': self.signature
        }
    
    @classmethod
    def from_dict(cls, vote_dict: Dict) -> 'Vote':
        """从字典创建投票"""
        vote = cls(
            validator=vote_dict['validator'],
            block_hash=vote_dict['block_hash'],
            height=vote_dict['height'],
            round_num=vote_dict['round'],
            vote_type=vote_dict['type']
        )
        vote.timestamp = vote_dict['timestamp']
        vote.signature = vote_dict['signature']
        return vote

class TendermintConsensus:
    """Tendermint共识机制类"""
    
    def __init__(self, blockchain: Blockchain, node_id: str):
        """
        初始化Tendermint共识
        
        Args:
            blockchain: 区块链实例
            node_id: 节点ID
        """
        self.blockchain = blockchain
        self.node_id = node_id
        
        # 共识状态
        self.state = ConsensusState.NEW_HEIGHT
        self.height = len(blockchain.chain)  # 当前高度
        self.round = 0  # 当前轮次
        
        # 验证者和质押信息
        self.validators = {}  # 地址 -> 质押金额
        self.total_stake = 0  # 总质押金额
        
        # 当前轮次的提议区块
        self.current_proposal = None
        
        # 投票存储
        self.prevotes = {}  # (height, round) -> {validator -> vote}
        self.precommits = {}  # (height, round) -> {validator -> vote}
        
        # 锁定信息
        self.locked_round = -1
        self.locked_block = None
        
        # 超时设置
        self.propose_timeout = 30  # 提议阶段超时（秒）
        self.prevote_timeout = 10  # 预投票阶段超时（秒）
        self.precommit_timeout = 10  # 预提交阶段超时（秒）
        
        # 超时计时器
        self.last_state_change_time = time.time()
        
        # 初始化验证者（在实际系统中，这应该从区块链状态加载）
        self.initialize_validators()
    
    def initialize_validators(self) -> None:
        """初始化验证者列表"""
        # 在实际系统中，这应该从区块链状态加载
        # 这里简单地添加一些测试验证者
        self.add_validator(self.node_id, 100.0)  # 添加自己作为验证者
    
    def add_validator(self, address: str, stake_amount: float) -> None:
        """
        添加验证者
        
        Args:
            address: 验证者地址
            stake_amount: 质押金额
        """
        self.validators[address] = stake_amount
        self.total_stake += stake_amount
        print(f"添加验证者 {address}，质押金额: {stake_amount}")
    
    def remove_validator(self, address: str) -> None:
        """
        移除验证者
        
        Args:
            address: 验证者地址
        """
        if address in self.validators:
            stake_amount = self.validators[address]
            self.total_stake -= stake_amount
            del self.validators[address]
            print(f"移除验证者 {address}，质押金额: {stake_amount}")
    
    def start_consensus(self) -> None:
        """启动共识过程"""
        self.state = ConsensusState.NEW_HEIGHT
        self.height = len(self.blockchain.chain)
        self.round = 0
        self.locked_round = -1
        self.locked_block = None
        self.current_proposal = None
        
        print(f"开始新的共识过程，高度: {self.height}, 轮次: {self.round}")
        
        # 进入提议阶段
        self.enter_propose()
    
    def enter_propose(self) -> None:
        """进入提议阶段"""
        self.state = ConsensusState.PROPOSE
        self.last_state_change_time = time.time()
        
        print(f"进入提议阶段，高度: {self.height}, 轮次: {self.round}")
        
        # 检查是否是当前轮次的提议者
        proposer = self.get_proposer(self.height, self.round)
        
        if proposer == self.node_id:
            print(f"节点 {self.node_id} 是当前轮次的提议者")
            
            # 创建提议区块
            proposed_block = self.create_proposal()
            
            if proposed_block:
                self.current_proposal = proposed_block
                
                # 广播提议
                self.broadcast_proposal(proposed_block)
                
                # 自动为自己的提议投票
                self.prevote(proposed_block.hash)
            else:
                # 如果无法创建提议，则投空票
                self.prevote(None)
        else:
            print(f"等待提议者 {proposer} 的提议")
            # 设置提议超时
            # 在实际实现中，这里应该启动一个定时器
    
    def create_proposal(self) -> Optional[Block]:
        """
        创建提议区块
        
        Returns:
            Optional[Block]: 提议的区块，如果无法创建则返回None
        """
        # 如果已经锁定了区块，则使用锁定的区块
        if self.locked_block and self.locked_round >= 0:
            print(f"使用锁定的区块作为提议，锁定轮次: {self.locked_round}")
            return self.locked_block
        
        # 否则创建新区块
        try:
            new_block = self.blockchain.create_block(self.node_id)
            print(f"创建新的提议区块: {new_block.hash[:8]}")
            return new_block
        except Exception as e:
            print(f"创建提议区块失败: {e}")
            return None
    
    def receive_proposal(self, block: Block, proposer: str) -> None:
        """
        接收提议
        
        Args:
            block: 提议的区块
            proposer: 提议者地址
        """
        # 验证提议者是否是当前轮次的指定提议者
        expected_proposer = self.get_proposer(self.height, self.round)
        
        if proposer != expected_proposer:
            print(f"提议者 {proposer} 不是当前轮次的指定提议者 {expected_proposer}")
            return
        
        # 验证区块
        if not self.validate_proposal(block):
            print(f"提议区块验证失败: {block.hash[:8]}")
            return
        
        print(f"接收到有效提议: {block.hash[:8]}")
        
        # 保存提议
        self.current_proposal = block
        
        # 如果已经锁定了区块，则只对锁定的区块投票
        if self.locked_block and self.locked_round >= 0:
            if block.hash == self.locked_block.hash:
                self.prevote(block.hash)
            else:
                self.prevote(self.locked_block.hash)
        else:
            # 否则对当前提议投票
            self.prevote(block.hash)
    
    def validate_proposal(self, block: Block) -> bool:
        """
        验证提议区块
        
        Args:
            block: 提议的区块
            
        Returns:
            bool: 区块是否有效
        """
        # 验证区块高度
        if block.index != self.height:
            print(f"区块高度不匹配: {block.index} != {self.height}")
            return False
        
        # 验证前一个区块哈希
        if block.previous_hash != self.blockchain.get_latest_block().hash:
            print(f"前一个区块哈希不匹配")
            return False
        
        # 验证区块哈希
        if block.hash != block.calculate_hash():
            print(f"区块哈希无效")
            return False
        
        # 验证交易
        for tx in block.transactions:
            if not tx.is_valid():
                print(f"交易无效: {tx.transaction_id}")
                return False
        
        return True
    
    def prevote(self, block_hash: Optional[str]) -> None:
        """
        进行预投票
        
        Args:
            block_hash: 区块哈希，如果为None则表示投空票
        """
        self.state = ConsensusState.PREVOTE
        self.last_state_change_time = time.time()
        
        # 如果投空票，使用特殊值
        vote_hash = block_hash if block_hash else "NIL"
        
        print(f"进行预投票，高度: {self.height}, 轮次: {self.round}, 投票: {vote_hash[:8] if vote_hash != 'NIL' else 'NIL'}")
        
        # 创建投票
        vote = Vote(
            validator=self.node_id,
            block_hash=vote_hash,
            height=self.height,
            round_num=self.round,
            vote_type="prevote"
        )
        
        # 保存自己的投票
        key = (self.height, self.round)
        if key not in self.prevotes:
            self.prevotes[key] = {}
        self.prevotes[key][self.node_id] = vote
        
        # 广播投票
        self.broadcast_vote(vote)
        
        # 检查是否已经收到超过2/3的预投票
        self.check_prevote_quorum()
    
    def receive_prevote(self, vote: Vote) -> None:
        """
        接收预投票
        
        Args:
            vote: 预投票
        """
        # 验证投票
        if not self.validate_vote(vote):
            print(f"预投票验证失败: {vote.validator}")
            return
        
        # 只处理当前高度和轮次的投票
        if vote.height != self.height or vote.round != self.round:
            print(f"忽略过期的预投票: 高度={vote.height}, 轮次={vote.round}")
            return
        
        print(f"接收到预投票: {vote.validator}, 投票: {vote.block_hash[:8] if vote.block_hash != 'NIL' else 'NIL'}")
        
        # 保存投票
        key = (vote.height, vote.round)
        if key not in self.prevotes:
            self.prevotes[key] = {}
        self.prevotes[key][vote.validator] = vote
        
        # 检查是否已经收到超过2/3的预投票
        self.check_prevote_quorum()
    
    def check_prevote_quorum(self) -> None:
        """检查是否达到预投票法定人数"""
        key = (self.height, self.round)
        
        if key not in self.prevotes:
            return
        
        votes = self.prevotes[key]
        
        # 计算投票权重
        vote_counts = {}
        total_voted_stake = 0
        
        for validator, vote in votes.items():
            if validator in self.validators:
                stake = self.validators[validator]
                total_voted_stake += stake
                
                if vote.block_hash not in vote_counts:
                    vote_counts[vote.block_hash] = 0
                vote_counts[vote.block_hash] += stake
        
        # 检查是否有区块获得超过2/3的投票
        quorum_threshold = self.total_stake * 2 / 3
        
        for block_hash, vote_stake in vote_counts.items():
            if vote_stake > quorum_threshold:
                print(f"区块 {block_hash[:8] if block_hash != 'NIL' else 'NIL'} 获得超过2/3的预投票")
                
                # 如果是空票，则进入下一轮
                if block_hash == "NIL":
                    self.start_new_round()
                    return
                
                # 锁定区块
                if self.current_proposal and self.current_proposal.hash == block_hash:
                    self.locked_round = self.round
                    self.locked_block = self.current_proposal
                
                # 进入预提交阶段
                self.precommit(block_hash)
                return
        
        # 如果总投票权重超过2/3但没有单一选项获得超过2/3，则进入下一轮
        if total_voted_stake > quorum_threshold:
            print(f"没有区块获得超过2/3的预投票，进入下一轮")
            self.start_new_round()
    
    def precommit(self, block_hash: str) -> None:
        """
        进行预提交
        
        Args:
            block_hash: 区块哈希
        """
        self.state = ConsensusState.PRECOMMIT
        self.last_state_change_time = time.time()
        
        print(f"进行预提交，高度: {self.height}, 轮次: {self.round}, 投票: {block_hash[:8] if block_hash != 'NIL' else 'NIL'}")
        
        # 创建投票
        vote = Vote(
            validator=self.node_id,
            block_hash=block_hash,
            height=self.height,
            round_num=self.round,
            vote_type="precommit"
        )
        
        # 保存自己的投票
        key = (self.height, self.round)
        if key not in self.precommits:
            self.precommits[key] = {}
        self.precommits[key][self.node_id] = vote
        
        # 广播投票
        self.broadcast_vote(vote)
        
        # 检查是否已经收到超过2/3的预提交
        self.check_precommit_quorum()
    
    def receive_precommit(self, vote: Vote) -> None:
        """
        接收预提交
        
        Args:
            vote: 预提交
        """
        # 验证投票
        if not self.validate_vote(vote):
            print(f"预提交验证失败: {vote.validator}")
            return
        
        # 只处理当前高度和轮次的投票
        if vote.height != self.height or vote.round != self.round:
            print(f"忽略过期的预提交: 高度={vote.height}, 轮次={vote.round}")
            return
        
        print(f"接收到预提交: {vote.validator}, 投票: {vote.block_hash[:8] if vote.block_hash != 'NIL' else 'NIL'}")
        
        # 保存投票
        key = (vote.height, vote.round)
        if key not in self.precommits:
            self.precommits[key] = {}
        self.precommits[key][vote.validator] = vote
        
        # 检查是否已经收到超过2/3的预提交
        self.check_precommit_quorum()
    
    def check_precommit_quorum(self) -> None:
        """检查是否达到预提交法定人数"""
        key = (self.height, self.round)
        
        if key not in self.precommits:
            return
        
        votes = self.precommits[key]
        
        # 计算投票权重
        vote_counts = {}
        total_voted_stake = 0
        
        for validator, vote in votes.items():
            if validator in self.validators:
                stake = self.validators[validator]
                total_voted_stake += stake
                
                if vote.block_hash not in vote_counts:
                    vote_counts[vote.block_hash] = 0
                vote_counts[vote.block_hash] += stake
        
        # 检查是否有区块获得超过2/3的投票
        quorum_threshold = self.total_stake * 2 / 3
        
        for block_hash, vote_stake in vote_counts.items():
            if vote_stake > quorum_threshold:
                print(f"区块 {block_hash[:8] if block_hash != 'NIL' else 'NIL'} 获得超过2/3的预提交")
                
                # 如果是空票，则进入下一轮
                if block_hash == "NIL":
                    self.start_new_round()
                    return
                
                # 提交区块
                self.commit_block(block_hash)
                return
        
        # 如果总投票权重超过2/3但没有单一选项获得超过2/3，则进入下一轮
        if total_voted_stake > quorum_threshold:
            print(f"没有区块获得超过2/3的预提交，进入下一轮")
            self.start_new_round()
    
    def commit_block(self, block_hash: str) -> None:
        """
        提交区块
        
        Args:
            block_hash: 区块哈希
        """
        self.state = ConsensusState.COMMIT
        
        print(f"提交区块，高度: {self.height}, 轮次: {self.round}, 区块: {block_hash[:8]}")
        
        # 获取要提交的区块
        block_to_commit = None
        
        if self.current_proposal and self.current_proposal.hash == block_hash:
            block_to_commit = self.current_proposal
        elif self.locked_block and self.locked_block.hash == block_hash:
            block_to_commit = self.locked_block
        
        if not block_to_commit:
            print(f"无法找到要提交的区块: {block_hash[:8]}")
            self.start_new_round()
            return
        
        # 添加区块到区块链
        if self.blockchain.add_block(block_to_commit):
            print(f"成功提交区块: {block_hash[:8]}")
            
            # 广播新区块
            self.broadcast_block(block_to_commit)
            
            # 使用定时器延迟启动新高度，避免递归
            import threading
            threading.Timer(180, self.start_new_height).start()
        else:
            print(f"提交区块失败: {block_hash[:8]}")
            self.start_new_round()
    
    def start_new_height(self) -> None:
        """开始新的高度"""
        self.state = ConsensusState.NEW_HEIGHT
        self.height = len(self.blockchain.chain)
        self.round = 0
        self.locked_round = -1
        self.locked_block = None
        self.current_proposal = None
        
        print(f"开始新的高度: {self.height}")
        
        # 使用定时器延迟进入提议阶段，避免递归
        import threading
        threading.Timer(180, self.enter_propose).start()
    
    def start_new_round(self) -> None:
        """开始新的轮次"""
        self.round += 1
        
        print(f"开始新的轮次，高度: {self.height}, 轮次: {self.round}")
        
        # 进入提议阶段
        self.enter_propose()
    
    def get_proposer(self, height: int, round_num: int) -> str:
        """
        获取指定高度和轮次的提议者
        
        Args:
            height: 区块高度
            round_num: 轮次
            
        Returns:
            str: 提议者地址
        """
        # 使用确定性算法选择提议者
        if not self.validators:
            return self.node_id
        
        # 按质押金额排序验证者
        sorted_validators = sorted(self.validators.items(), key=lambda x: (-x[1], x[0]))
        validator_addresses = [v[0] for v in sorted_validators]
        
        # 使用高度和轮次作为种子
        seed = f"{height}_{round_num}"
        seed_hash = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
        
        # 选择提议者
        index = seed_hash % len(validator_addresses)
        return validator_addresses[index]
    
    def validate_vote(self, vote: Vote) -> bool:
        """
        验证投票
        
        Args:
            vote: 投票
            
        Returns:
            bool: 投票是否有效
        """
        # 验证投票者是否是验证者
        if vote.validator not in self.validators:
            print(f"投票者 {vote.validator} 不是验证者")
            return False
        
        # 验证签名
        vote_data = f"{vote.validator}_{vote.block_hash}_{vote.height}_{vote.round}_{vote.type}_{vote.timestamp}"
        expected_signature = hashlib.sha256(vote_data.encode()).hexdigest()
        
        if vote.signature != expected_signature:
            print(f"投票签名无效")
            return False
        
        return True
    
    def check_timeout(self) -> None:
        """检查超时"""
        current_time = time.time()
        elapsed_time = current_time - self.last_state_change_time
        
        if self.state == ConsensusState.PROPOSE and elapsed_time > self.propose_timeout:
            print(f"提议阶段超时，进行空投票")
            self.prevote(None)
        elif self.state == ConsensusState.PREVOTE and elapsed_time > self.prevote_timeout:
            print(f"预投票阶段超时，进入下一轮")
            self.start_new_round()
        elif self.state == ConsensusState.PRECOMMIT and elapsed_time > self.precommit_timeout:
            print(f"预提交阶段超时，进入下一轮")
            self.start_new_round()
    
    # 以下方法需要与P2P网络集成
    
    def broadcast_proposal(self, block: Block) -> None:
        """
        广播提议
        
        Args:
            block: 提议的区块
        """
        # 在实际实现中，这里应该调用P2P网络的广播方法
        print(f"广播提议: {block.hash[:8]}")
    
    def broadcast_vote(self, vote: Vote) -> None:
        """
        广播投票
        
        Args:
            vote: 投票
        """
        # 在实际实现中，这里应该调用P2P网络的广播方法
        print(f"广播投票: {vote.type}, {vote.block_hash[:8] if vote.block_hash != 'NIL' else 'NIL'}")
    
    def broadcast_block(self, block: Block) -> None:
        """
        广播区块
        
        Args:
            block: 区块
        """
        # 在实际实现中，这里应该调用P2P网络的广播方法
        print(f"广播区块: {block.hash[:8]}")