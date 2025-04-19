# wallet_cli.py

import argparse
import sys
import time
from typing import List, Dict, Any, Optional
import os

from wallet import WalletManager, Wallet
from Node import Node
from mining_rewards import RewardCalculator, RewardDistributor
from pos_consensus import POSConsensus
from bill_hash import BillManager

class WalletCLI:
    """钱包命令行界面"""
    
    def __init__(self):
        """初始化钱包CLI"""
        self.wallet_manager = WalletManager()
        self.current_wallet = None
        self.node = None
        self.data_dir = "blockchain_data"
        
        # 创建数据目录
        os.makedirs(self.data_dir, exist_ok=True)
    
    def start_node(self, host: str = "127.0.0.1", port: int = 5000) -> None:
        """
        启动本地节点
        
        Args:
            host: 主机地址
            port: 端口号
        """
        if self.node:
            print("节点已经在运行")
            return
        
        # 使用当前钱包地址作为节点ID
        node_id = self.current_wallet.address if self.current_wallet else f"Node_CLI_{port}"
        
        self.node = Node(node_id, host, port)
        self.node.start()
        
        # 如果有当前钱包，设置节点的余额为钱包余额
        if self.current_wallet:
            # 同步质押状态
            if self.current_wallet.staked_amount > 0:
                self.node.staked_amount = self.current_wallet.staked_amount
                self.node.pos_consensus.add_stake(self.current_wallet.address, self.current_wallet.staked_amount)
        
        print(f"本地节点 {node_id} 已启动，地址: {host}:{port}")
    
    def connect_to_network(self, seed_host: str, seed_port: int) -> None:
        """
        连接到网络
        
        Args:
            seed_host: 种子节点主机地址
            seed_port: 种子节点端口号
        """
        if not self.node:
            print("请先启动本地节点")
            return
        
        if self.node.connect_to_network(seed_host, seed_port):
            print(f"已连接到网络节点 {seed_host}:{seed_port}")
            
            # 连接成功后自动发现其他节点
            self.node.auto_discover_nodes()
            
            # 同步区块链
            self.node.p2p_node.synchronize_blockchain()
        else:
            print(f"连接到网络节点 {seed_host}:{seed_port} 失败")
    
    def create_wallet(self, name: str = None) -> None:
        """
        创建钱包
        
        Args:
            name: 钱包名称
        """
        try:
            wallet = self.wallet_manager.create_wallet(name)
            self.current_wallet = wallet
            print(f"已创建并选择钱包: {wallet.name}, 地址: {wallet.address}")
            
            # 如果节点已启动，更新节点ID
            if self.node:
                self.node.node_id = wallet.address
                print(f"已更新节点ID为钱包地址: {wallet.address}")
        except Exception as e:
            print(f"创建钱包失败: {e}")
    
    def list_wallets(self) -> None:
        """列出所有钱包"""
        wallets = self.wallet_manager.list_wallets()
        
        if not wallets:
            print("没有找到钱包")
            return
        
        print("\n可用钱包:")
        for i, wallet in enumerate(wallets):
            current = " (当前)" if self.current_wallet and self.current_wallet.name == wallet['name'] else ""
            print(f"{i+1}. {wallet['name']} - {wallet['address']}{current}")
    
    def select_wallet(self, name: str) -> None:
        """
        选择钱包
        
        Args:
            name: 钱包名称
        """
        wallet = self.wallet_manager.get_wallet(name)
        
        if wallet:
            self.current_wallet = wallet
            print(f"已选择钱包: {wallet.name}, 地址: {wallet.address}")
            
            # 如果节点已启动，更新节点ID
            if self.node:
                self.node.node_id = wallet.address
                print(f"已更新节点ID为钱包地址: {wallet.address}")
                
                # 同步质押状态
                if wallet.staked_amount > 0:
                    self.node.staked_amount = wallet.staked_amount
                    self.node.pos_consensus.add_stake(wallet.address, wallet.staked_amount)
        else:
            print(f"钱包 {name} 不存在")
    
    def get_balance(self) -> None:
        """获取当前钱包余额"""
        if not self.current_wallet:
            print("请先选择钱包")
            return
        
        if not self.node:
            print("请先启动本地节点")
            return
        
        balance = self.current_wallet.get_balance(self.node)
        staked = self.current_wallet.get_staked_amount()
        total = balance + staked
        
        print(f"钱包 {self.current_wallet.name} 信息:")
        print(f"可用余额: {balance}")
        print(f"质押金额: {staked}")
        print(f"总资产: {total}")
    
    def create_transaction(self, recipient: str, amount: float, fee: float = 0.001) -> None:
        """
        创建交易
        
        Args:
            recipient: 接收方地址
            amount: 交易金额
            fee: 交易费用
        """
        if not self.current_wallet:
            print("请先选择钱包")
            return
        
        if not self.node:
            print("请先启动本地节点")
            return
        
        try:
            # 检查余额
            balance = self.current_wallet.get_balance(self.node)
            total_amount = amount + fee
            
            if balance < total_amount:
                print(f"余额不足: {balance} < {total_amount}")
                return
            
            # 创建交易
            transaction = self.current_wallet.create_transaction(
                recipient=recipient,
                amount=amount,
                fee=fee,
                node=self.node
            )
            
            print(f"交易已创建: {transaction.transaction_id}")
            print(f"发送方: {transaction.sender}")
            print(f"接收方: {transaction.recipient}")
            print(f"金额: {transaction.amount}")
            print(f"费用: {transaction.fee}")
        except Exception as e:
            print(f"创建交易失败: {e}")
    
    def create_bill(self, payee: str, amount: float, description: str) -> None:
        """
        创建账单
        
        Args:
            payee: 收款方地址
            amount: 金额
            description: 描述
        """
        if not self.current_wallet:
            print("请先选择钱包")
            return
        
        try:
            bill = self.current_wallet.create_bill(payee, amount, description)
            print(f"账单已创建: {bill.bill_id}")
            print(f"付款方: {bill.payer}")
            print(f"收款方: {bill.payee}")
            print(f"金额: {bill.amount}")
            print(f"描述: {bill.description}")
            print(f"哈希: {bill.hash}")
        except Exception as e:
            print(f"创建账单失败: {e}")
    
    def pay_bill(self, bill_id: str) -> None:
        """
        支付账单
        
        Args:
            bill_id: 账单ID
        """
        if not self.current_wallet:
            print("请先选择钱包")
            return
        
        if not self.node:
            print("请先启动本地节点")
            return
        
        # 获取账单
        bill = self.current_wallet.bill_manager.get_bill(bill_id)
        
        if not bill:
            print(f"账单 {bill_id} 不存在")
            return
        
        # 支付账单
        transaction = self.current_wallet.pay_bill(bill, self.node)
        
        if transaction:
            print(f"账单 {bill_id} 已支付，交易ID: {transaction.transaction_id}")
        else:
            print(f"支付账单 {bill_id} 失败")
    
    def stake_tokens(self, amount: float) -> None:
        """
        质押代币
        
        Args:
            amount: 质押金额
        """
        if not self.current_wallet:
            print("请先选择钱包")
            return
        
        if not self.node:
            print("请先启动本地节点")
            return
        
        # 质押代币
        if self.current_wallet.stake_tokens(amount, self.node):
            print(f"已质押 {amount} 代币")
            
            # 广播验证者信息
            if self.node.node_id in self.node.pos_consensus.validators:
                self.node.p2p_node.broadcast_validator_info(
                    self.current_wallet.staked_amount,
                    self.node.pos_consensus
                )
        else:
            print(f"质押代币失败")
    
    def unstake_tokens(self, amount: float) -> None:
        """
        取消质押
        
        Args:
            amount: 取消质押的金额
        """
        if not self.current_wallet:
            print("请先选择钱包")
            return
        
        if not self.node:
            print("请先启动本地节点")
            return
        
        # 取消质押
        if self.current_wallet.unstake_tokens(amount, self.node):
            print(f"已取消质押 {amount} 代币")
        else:
            print(f"取消质押失败")
    
    def get_blockchain_info(self) -> None:
        """获取区块链信息"""
        if not self.node:
            print("请先启动本地节点")
            return
        
        info = self.node.get_blockchain_info()
        print("\n区块链信息:")
        print(f"链长度: {info['chain_length']}")
        print(f"待处理交易: {info['pending_transactions']}")
        print(f"链是否有效: {info['is_valid']}")
        
        # 显示最新区块信息
        if info['chain_length'] > 0:
            latest_block = self.node.blockchain.get_latest_block()
            print("\n最新区块信息:")
            print(f"区块索引: {latest_block.index}")
            print(f"区块哈希: {latest_block.hash}")
            print(f"验证者: {latest_block.validator}")
            print(f"交易数量: {len(latest_block.transactions)}")
            print(f"时间戳: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest_block.timestamp))}")
    
    def get_validator_info(self) -> None:
        """获取验证者信息"""
        if not self.node:
            print("请先启动本地节点")
            return
        
        validators = self.node.get_validator_info()
        
        if not validators:
            print("没有验证者")
            return
        
        print("\n验证者信息:")
        for i, validator in enumerate(validators):
            is_current = " (当前钱包)" if self.current_wallet and validator['address'] == self.current_wallet.address else ""
            print(f"{i+1}. 地址: {validator['address']}{is_current}")
            print(f"   质押金额: {validator['stake_amount']}")
            print(f"   质押年龄: {validator['stake_age']:.2f} 天")
            print(f"   权重: {validator['weight']:.2f}")
    
    def get_network_info(self) -> None:
        """获取网络信息"""
        if not self.node:
            print("请先启动本地节点")
            return
        
        peers = self.node.p2p_node.peers
        
        print("\n网络信息:")
        print(f"本地节点: {self.node.node_id} ({self.node.host}:{self.node.port})")
        print(f"已连接节点数: {len(peers)}")
        
        if peers:
            print("\n已连接节点:")
            for i, (peer_id, (host, port)) in enumerate(peers.items()):
                print(f"{i+1}. {peer_id} ({host}:{port})")
    
    def export_wallet(self, export_path: str = None) -> None:
        """
        导出钱包
        
        Args:
            export_path: 导出路径
        """
        if not self.current_wallet:
            print("请先选择钱包")
            return
        
        if not export_path:
            export_path = f"{self.current_wallet.name}_exported.json"
        
        try:
            # 复制钱包文件
            wallet_path = os.path.join(self.current_wallet.wallet_dir, f"{self.current_wallet.name}.json")
            with open(wallet_path, 'r') as src, open(export_path, 'w') as dst:
                dst.write(src.read())
            
            print(f"钱包已导出到: {export_path}")
        except Exception as e:
            print(f"导出钱包失败: {e}")
    
    def import_wallet(self, import_path: str) -> None:
        """
        导入钱包
        
        Args:
            import_path: 导入路径
        """
        try:
            # 读取导入文件
            with open(import_path, 'r') as f:
                wallet_data = json.loads(f.read())
            
            # 获取钱包名称
            name = wallet_data.get('name')
            
            if not name:
                print("导入文件中没有钱包名称")
                return
            
            # 检查钱包是否已存在
            if name in self.wallet_manager.wallets:
                print(f"钱包 {name} 已存在，请先删除或重命名")
                return
            
            # 复制钱包文件
            wallet_path = os.path.join(self.wallet_manager.wallet_dir, f"{name}.json")
            with open(import_path, 'r') as src, open(wallet_path, 'w') as dst:
                dst.write(src.read())
            
            # 重新加载钱包
            self.wallet_manager._load_wallets()
            
            print(f"钱包 {name} 已导入")
            
            # 选择导入的钱包
            self.select_wallet(name)
        except Exception as e:
            print(f"导入钱包失败: {e}")
    
    def run_cli(self) -> None:
        """运行命令行界面"""
        print("欢迎使用区块链钱包CLI")
        
        while True:
            print("\n" + "="*50)
            print("区块链钱包CLI")
            print("="*50)
            
            if self.current_wallet:
                print(f"当前钱包: {self.current_wallet.name} ({self.current_wallet.address})")
                if self.node:
                    balance = self.current_wallet.get_balance(self.node)
                    staked = self.current_wallet.get_staked_amount()
                    print(f"可用余额: {balance}, 质押金额: {staked}, 总资产: {balance + staked}")
            else:
                print("当前未选择钱包")
            
            if self.node:
                print(f"本地节点: {self.node.node_id} ({self.node.host}:{self.node.port})")
                print(f"已连接节点数: {len(self.node.p2p_node.peers)}")
            else:
                print("本地节点未启动")
            
            print("\n可用命令:")
            print("1. 启动本地节点")
            print("2. 连接到网络")
            print("3. 创建钱包")
            print("4. 列出钱包")
            print("5. 选择钱包")
            print("6. 查看余额")
            print("7. 创建交易")
            print("8. 创建账单")
            print("9. 支付账单")
            print("10. 质押代币")
            print("11. 取消质押")
            print("12. 查看区块链信息")
            print("13. 查看验证者信息")
            print("14. 查看网络信息")
            print("15. 导出钱包")
            print("16. 导入钱包")
            print("0. 退出")
            
            choice = input("\n请输入命令编号: ")
            
            if choice == "1":
                host = input("请输入主机地址 (默认 127.0.0.1): ") or "127.0.0.1"
                port = int(input("请输入端口号 (默认 5000): ") or "5000")
                self.start_node(host, port)
            
            elif choice == "2":
                seed_host = input("请输入种子节点主机地址: ")
                seed_port = int(input("请输入种子节点端口号: "))
                self.connect_to_network(seed_host, seed_port)
            
            elif choice == "3":
                name = input("请输入钱包名称 (留空自动生成): ")
                self.create_wallet(name or None)
            
            elif choice == "4":
                self.list_wallets()
            
            elif choice == "5":
                name = input("请输入钱包名称: ")
                self.select_wallet(name)
            
            elif choice == "6":
                self.get_balance()
            
            elif choice == "7":
                recipient = input("请输入接收方地址: ")
                amount = float(input("请输入交易金额: "))
                fee = float(input("请输入交易费用 (默认 0.001): ") or "0.001")
                self.create_transaction(recipient, amount, fee)
            
            elif choice == "8":
                payee = input("请输入收款方地址: ")
                amount = float(input("请输入金额: "))
                description = input("请输入描述: ")
                self.create_bill(payee, amount, description)
            
            elif choice == "9":
                bill_id = input("请输入账单ID: ")
                self.pay_bill(bill_id)
            
            elif choice == "10":
                amount = float(input("请输入质押金额: "))
                self.stake_tokens(amount)
            
            elif choice == "11":
                amount = float(input("请输入取消质押的金额: "))
                self.unstake_tokens(amount)
            
            elif choice == "12":
                self.get_blockchain_info()
            
            elif choice == "13":
                self.get_validator_info()
            
            elif choice == "14":
                self.get_network_info()
            
            elif choice == "15":
                export_path = input("请输入导出路径 (留空使用默认路径): ")
                self.export_wallet(export_path or None)
            
            elif choice == "16":
                import_path = input("请输入导入路径: ")
                self.import_wallet(import_path)
            
            elif choice == "0":
                print("感谢使用区块链钱包CLI，再见！")
                if self.node:
                    self.node.stop()
                sys.exit(0)
            
            else:
                print("无效的命令，请重试")
            
            input("\n按回车键继续...")


if __name__ == "__main__":
    cli = WalletCLI()
    cli.run_cli()