# demo.py

import time
import threading
import random
import uuid
from typing import List, Dict, Any

from blockchain_core import Blockchain, Transaction
from p2p_network import P2PNode
from pos_consensus import POSConsensus
from mining_rewards import RewardCalculator, RewardDistributor
from bill_hash import BillManager, Bill

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
        self.p2p_node = P2PNode(host, port, node_id, self.blockchain)
        
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
    
    def start(self) -> None:
        """启动节点"""
        # 启动P2P网络
        self.p2p_node.start()
        
        self.running = True
        
        # 启动区块生成线程
        threading.Thread(target=self.block_generation_loop, daemon=True).start()
        
        print(f"节点 {self.node_id} 启动成功")
    
    def stop(self) -> None:
        """停止节点"""
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
        if amount <= 0:
            print("质押金额必须大于0")
            return False
        
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
        else:
            # 如果质押失败，恢复余额
            self.balance += amount
            self.staked_amount -= amount
            print(f"节点 {self.node_id} 质押失败")
        
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
                    print(f"节点 {self.node_id} 被选为验证者，生成新区块")
                    
                    # 生成新区块
                    new_block = self.pos_consensus.forge_block(self.node_id)
                    
                    if new_block:
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


def run_demo():
    """运行演示"""
    print("启动区块链演示...")
    
    # 创建节点
    nodes = []
    for i in range(3):
        node_id = f"Node_{i}"
        host = "127.0.0.1"
        port = 5002 + i
        node = Node(node_id, host, port)
        nodes.append(node)
        node.start()
        print(f"节点 {node_id} 启动，地址: {host}:{port}")
    
    # 连接节点
    for i in range(1, 3):
        nodes[i].connect_to_network("127.0.0.1", 5002)
        print(f"节点 {nodes[i].node_id} 连接到节点 {nodes[0].node_id}")
    
    # 质押代币
    for node in nodes:
        stake_amount = random.uniform(10, 50)
        node.stake(stake_amount)
    
    # 创建一些交易
    for _ in range(5):
        sender_idx = random.randint(0, 2)
        recipient_idx = random.randint(0, 2)
        while recipient_idx == sender_idx:
            recipient_idx = random.randint(0, 2)
        
        amount = random.uniform(1, 5)
        nodes[sender_idx].create_transaction(nodes[recipient_idx].node_id, amount)
    
    # 创建并支付账单
    for _ in range(3):
        payer_idx = random.randint(0, 2)
        payee_idx = random.randint(0, 2)
        while payee_idx == payer_idx:
            payee_idx = random.randint(0, 2)
        
        amount = random.uniform(1, 3)
        description = f"Payment for service #{uuid.uuid4().hex[:8]}"
        
        bill = nodes[payer_idx].create_bill(nodes[payee_idx].node_id, amount, description)
        nodes[payer_idx].pay_bill(bill)
    
    # 等待一段时间，让区块生成
    print("等待区块生成...")
    time.sleep(10)
    
    # 显示节点信息
    for node in nodes:
        print(f"\n节点 {node.node_id} 信息:")
        print(f"余额: {node.get_balance()}")
        print(f"质押金额: {node.get_staked_amount()}")
        print(f"区块链信息: {node.get_blockchain_info()}")
        print(f"验证者信息: {node.get_validator_info()}")
    
    # 停止节点
    for node in nodes:
        node.stop()
    
    print("演示结束")
    exit(0)


if __name__ == "__main__":
    run_demo()
