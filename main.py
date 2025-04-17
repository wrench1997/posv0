

import time
import threading
import random
import uuid
from typing import List, Dict, Any

from blockchain_core import Blockchain, Transaction,Block
from p2p_network import P2PNode

from pos_consensus import POSConsensus
from mining_rewards import RewardCalculator, RewardDistributor
from bill_hash import BillManager, Bill
from blockchain_storage import BlockchainStorage

class Node:
    """节点类，整合所有模块"""
    
    def __init__(self, node_id: str, host: str, port: int, initial_balance: float = 100.0):
        """
        初始化节点
        
        Args:
            node_id: 节点ID
            host: 主机地址
            port: 端口号
            initial_balance: 初始余额
        """
        self.node_id = node_id
        self.host = host
        self.port = port
        self.balance = initial_balance
        
        # 初始化区块链
        self.blockchain = Blockchain()
        
        # 初始化P2P网络
        self.p2p_node = P2PNode(host, port, node_id, self.blockchain, self)
        
        # 初始化POS共识机制
        self.pos_consensus = POSConsensus(self.blockchain)
        
        # 初始化奖励计算器和分配器
        self.reward_calculator = RewardCalculator()
        self.reward_distributor = RewardDistributor(self.blockchain, self.reward_calculator)
        
        # 初始化账单管理器
        self.bill_manager = BillManager()
        
        # 节点运行标志
        self.running = False
        
        # 质押金额
        self.staked_amount = 0.0
        
        # 添加区块链存储
        self.blockchain_storage = BlockchainStorage()
        
        # 尝试加载已有区块链数据
        loaded_blockchain = self.blockchain_storage.load_blockchain(node_id)
        if loaded_blockchain:
            # Instead of replacing the entire blockchain object, just load the chain
            if self.blockchain.load_saved_chain(loaded_blockchain.chain):
                print(f"Successfully loaded valid blockchain data, chain length: {len(self.blockchain.chain)}")
                
                # Also load pending transactions
                self.blockchain.pending_transactions = loaded_blockchain.pending_transactions
            else:
                print("Loaded blockchain data is invalid, using new blockchain")
        
        # 初始化Tendermint共识
        self.tendermint_consensus = TendermintConsensus(self.blockchain, node_id)
        
        # 添加消息处理器
        self.p2p_node.message_handlers.update({
            Message.TYPE_PROPOSAL: self.p2p_node.handle_proposal,
            Message.TYPE_PREVOTE: self.p2p_node.handle_prevote,
            Message.TYPE_PRECOMMIT: self.p2p_node.handle_precommit
        })

    
    # 在 main.py 中的 Node 类的 start 方法中添加

    def start(self) -> None:
        """启动节点"""
        # 确保区块链一致性
        self.ensure_blockchain_consistency()
        
        # 启动P2P网络
        self.p2p_node.start()
        
        self.running = True
        
        # 启动区块生成线程
        threading.Thread(target=self.block_generation_loop, daemon=True).start()
        
        # 启动自动保存线程
        threading.Thread(target=self.auto_save_loop, daemon=True).start()
        
        # 启动Tendermint共识
        threading.Thread(target=self.tendermint_consensus_loop, daemon=True).start()
        
        print(f"节点 {self.node_id} 启动成功，使用Tendermint共识")

    def tendermint_consensus_loop(self) -> None:
        """Tendermint共识循环"""
        # 等待P2P网络启动
        time.sleep(2)
        
        # 启动共识过程
        self.tendermint_consensus.start_consensus()
        
        # 定期检查超时
        while self.running:
            self.tendermint_consensus.check_timeout()
            time.sleep(1)

    def auto_save_loop(self) -> None:
        """自动保存循环"""
        save_interval = 300  # 5分钟保存一次
        
        while self.running:
            time.sleep(save_interval)
            if self.running:  # 再次检查，避免在关闭过程中保存
                self.save_blockchain_data()
                print(f"自动保存区块链数据完成，链长度: {len(self.blockchain.chain)}")

    def auto_discover_nodes(self) -> None:
        """自动发现网络中的节点"""
        if not self.p2p_node or not self.p2p_node.peers:
            print("节点未连接到网络，无法发现其他节点")
            return
        
        self.p2p_node.auto_discover_nodes()

    # 在 Node 类中添加验证工作量的方法
    def verify_work(self, block: Block) -> bool:
        """验证区块的工作量"""
        # 如果验证者不在本地验证者列表中，但区块来自网络，尝试从网络同步验证者信息
        if block.validator not in self.pos_consensus.validators:
            # 尝试同步验证者信息
            self.p2p_node.synchronize_validators()
            
            # 再次检查验证者
            if block.validator not in self.pos_consensus.validators:
                print(f"区块验证者 {block.validator} 不是有效的验证者")
                return False
        
        # 获取验证者的质押信息
        validator_stake = self.pos_consensus.stakes.get(block.validator)
        if not validator_stake:
            print(f"找不到验证者 {block.validator} 的质押信息")
            return False
        
        # 验证质押金额是否满足最低要求
        if validator_stake.amount < self.pos_consensus.min_stake_amount:
            print(f"验证者 {block.validator} 的质押金额 {validator_stake.amount} 低于最低要求 {self.pos_consensus.min_stake_amount}")
            return False
        
        # 验证区块哈希是否有效
        if block.hash != block.calculate_hash():
            print(f"区块哈希无效: {block.hash} != {block.calculate_hash()}")
            return False
        
        print(f"区块 {block.index} 的工作量验证通过，验证者: {block.validator}, 质押金额: {validator_stake.amount}")
        return True

    def stop(self) -> None:
        """停止节点"""
        # 保存区块链数据
        self.save_blockchain_data()
        
        self.running = False
        self.p2p_node.stop()
        print(f"节点 {self.node_id} 已停止")
    
    def connect_to_network(self, seed_host: str, seed_port: int) -> bool:
        """
        连接到网络
        
        Args:
            seed_host: 种子节点主机地址
            seed_port: 种子节点端口号
            
        Returns:
            bool: 连接是否成功
        """
        return self.p2p_node.connect_to_peer(seed_host, seed_port)
    
    def stake(self, amount: float) -> bool:
        """
        质押代币
        
        Args:
            amount: 质押金额
            
        Returns:
            bool: 质押是否成功
        """
        # if amount <= 0:
        #     print("质押金额必须大于0")
        #     return False
        
        if amount > self.balance:
            print(f"余额不足: {self.balance} < {amount}")
            return False
        
        # 减少余额
        self.balance -= amount
        
        # 增加质押金额
        self.staked_amount += amount
        
        # 添加质押
        success = self.pos_consensus.add_stake(self.node_id, amount)
        
        if success:
            print(f"节点 {self.node_id} 质押 {amount} 代币成功，当前质押: {self.staked_amount}，余额: {self.balance}")
            # 更新Tendermint验证者
            self.tendermint_consensus.add_validator(self.node_id, amount)
        else:
            # 如果质押失败，恢复余额
            self.balance += amount
            self.staked_amount -= amount
            print(f"节点 {self.node_id} 质押失败")

        # 如果成功成为验证者，广播验证者信息
        if success and self.node_id in self.pos_consensus.validators:
            self.p2p_node.broadcast_validator_info(self.staked_amount,self.pos_consensus)
        return success


    def unstake(self, amount: float) -> bool:
        """
        取消质押
        
        Args:
            amount: 取消质押的金额
            
        Returns:
            bool: 取消质押是否成功
        """
        if amount <= 0:
            print("取消质押金额必须大于0")
            return False
        
        if amount > self.staked_amount:
            print(f"质押金额不足: {self.staked_amount} < {amount}")
            return False
        
        # 移除质押
        success = self.pos_consensus.remove_stake(self.node_id, amount)
        
        if success:
            # 增加余额
            self.balance += amount
            
            # 减少质押金额
            self.staked_amount -= amount
            
            print(f"节点 {self.node_id} 取消质押 {amount} 代币成功，当前质押: {self.staked_amount}，余额: {self.balance}")
            
            # 更新Tendermint验证者
            if self.staked_amount == 0:
                self.tendermint_consensus.remove_validator(self.node_id)
            else:
                # 否则更新质押金额
                self.tendermint_consensus.validators[self.node_id] = self.staked_amount
        else:
            print(f"节点 {self.node_id} 取消质押失败")
        
        return success
    
    def create_transaction(self, recipient: str, amount: float) -> bool:
        """
        创建交易
        
        Args:
            recipient: 接收方地址
            amount: 交易金额
            
        Returns:
            bool: 交易是否成功创建
        """
        if amount <= 0:
            print("交易金额必须大于0")
            return False
        
        fee = 0.001  # 交易费用
        total_amount = amount + fee
        
        if total_amount > self.balance:
            print(f"余额不足: {self.balance} < {total_amount}")
            return False
        
        # 创建交易
        transaction = Transaction(self.node_id, recipient, amount, fee)
        
        # 签名交易（在实际系统中，这里应该使用私钥进行签名）
        transaction.sign_transaction(f"SIG_{self.node_id}_{int(time.time())}")
        
        # 添加交易到区块链
        if self.blockchain.add_transaction(transaction):
            # 减少余额
            self.balance -= total_amount
            
            # 广播交易
            self.p2p_node.broadcast_new_transaction(transaction)
            
            print(f"节点 {self.node_id} 创建交易: {transaction.transaction_id}，金额: {amount}，费用: {fee}")
            return True
        else:
            print(f"节点 {self.node_id} 创建交易失败")
            return False
    
    def create_bill(self, payee: str, amount: float, description: str) -> Bill:
        """
        创建账单
        
        Args:
            payee: 收款方
            amount: 金额
            description: 描述
            
        Returns:
            Bill: 创建的账单
        """
        bill = self.bill_manager.create_bill(self.node_id, payee, amount, description)
        print(f"节点 {self.node_id} 创建账单: {bill.bill_id}，金额: {amount}，收款方: {payee}")
        return bill
    
    def pay_bill(self, bill: Bill) -> bool:
        """
        支付账单
        
        Args:
            bill: 账单
            
        Returns:
            bool: 支付是否成功
        """
        # 验证账单
        if not self.bill_manager.verify_bill(bill):
            print(f"账单验证失败: {bill.bill_id}")
            return False
        
        # 将账单转换为交易数据
        transaction_data = self.bill_manager.bill_to_transaction(bill)
        
        # 创建交易
        return self.create_transaction(
            transaction_data['recipient'],
            transaction_data['amount']
        )
    
    def block_generation_loop(self) -> None:
        """区块生成循环"""
        while self.running:
            # 检查是否到了生成新区块的时间
            if self.pos_consensus.is_time_to_forge():
                # 选择验证者
                validator = self.pos_consensus.select_validator()
                
                if validator == self.node_id:
                    print(f"节点 {self.node_id} 被选为验证者，生成新区块\n")
                    
                    # 生成新区块
                    new_block = self.pos_consensus.forge_block(self.node_id)
                    
                    if new_block:
                        # 确保区块索引正确
                        expected_index = len(self.blockchain.chain)
                        if new_block.index != expected_index:
                            print(f"区块索引不匹配，期望 {expected_index}，实际 {new_block.index}，重新设置索引")
                            new_block.index = expected_index
                            new_block.hash = new_block.calculate_hash()
                        
                        # 添加奖励交易
                        self.reward_distributor.add_reward_transaction(new_block)
                        
                        # 添加区块到区块链
                        if self.blockchain.add_block(new_block):
                            # 广播新区块
                            self.p2p_node.broadcast_new_block(new_block)
                            
                            # 获取奖励
                            reward = self.reward_calculator.calculate_total_reward(new_block)
                            self.balance += reward
                            
                            print(f"节点 {self.node_id} 成功生成区块 {new_block.index}，获得奖励: {reward}")
                            
                            # 保存区块链数据
                            self.save_blockchain_data()
                        else:
                            print(f"节点 {self.node_id} 添加区块失败")
                    else:
                        print(f"节点 {self.node_id} 生成区块失败")
            
            # 休眠一段时间
            time.sleep(1)
    
    def get_balance(self) -> float:
        """
        获取余额
        
        Returns:
            float: 当前余额
        """
        return self.balance
    
    def get_staked_amount(self) -> float:
        """
        获取质押金额
        
        Returns:
            float: 当前质押金额
        """
        return self.staked_amount
    
    def get_blockchain_info(self) -> Dict[str, Any]:
        """
        获取区块链信息
        
        Returns:
            Dict[str, Any]: 区块链信息
        """
        return {
            'chain_length': len(self.blockchain.chain),
            'pending_transactions': len(self.blockchain.pending_transactions),
            'is_valid': self.blockchain.is_chain_valid()
        }
    
    def get_validator_info(self) -> List[Dict]:
        """
        获取验证者信息
        
        Returns:
            List[Dict]: 验证者信息列表
        """
        return self.pos_consensus.get_validator_info()
    
    # 添加保存区块链数据的方法
    def save_blockchain_data(self) -> bool:
        """保存区块链数据"""
        return self.blockchain_storage.save_blockchain(self.blockchain, self.node_id)


    def ensure_blockchain_consistency(self):
        """确保区块链状态一致性"""
        # 验证整个链
        if not self.blockchain.is_chain_valid():
            print("区块链状态不一致，尝试修复...")
            # 尝试修复区块链
            self.repair_blockchain()
        else:
            print("区块链状态一致")

    def repair_blockchain(self):
        """尝试修复区块链"""
        # 找到最后一个有效区块
        valid_chain_length = 0
        for i in range(len(self.blockchain.chain)):
            if i == 0 or (self.blockchain.chain[i].previous_hash == self.blockchain.chain[i-1].hash and 
                        self.blockchain.chain[i].hash == self.blockchain.chain[i].calculate_hash()):
                valid_chain_length = i + 1
            else:
                break
        
        if valid_chain_length < len(self.blockchain.chain):
            print(f"截断区块链至长度 {valid_chain_length}")
            # 保存被移除区块中的交易
            for block in self.blockchain.chain[valid_chain_length:]:
                for tx in block.transactions:
                    if tx.sender != "COINBASE" and not any(t.transaction_id == tx.transaction_id for t in self.blockchain.pending_transactions):
                        self.blockchain.pending_transactions.append(tx)
            
            # 截断链
            self.blockchain.chain = self.blockchain.chain[:valid_chain_length]
            
            # 保存修复后的区块链
            self.save_blockchain_data()
