# wallet.py

import hashlib
import json
import time
import uuid
import os
import base64
from typing import Dict, List, Any, Optional, Tuple
import random
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature

from blockchain_core import Transaction
from bill_hash import Bill, BillManager

class Wallet:
    """钱包类，管理用户的密钥和交易"""
    
    def __init__(self, name: str = None, load_existing: bool = False, wallet_dir: str = "wallets"):
        """
        初始化钱包
        
        Args:
            name: 钱包名称，如果为None则自动生成
            load_existing: 是否加载已存在的钱包
            wallet_dir: 钱包文件存储目录
        """
        self.wallet_dir = wallet_dir
        
        # 创建钱包目录
        os.makedirs(wallet_dir, exist_ok=True)

        # 初始化质押信息（无论是新钱包还是加载已有钱包）
        self.staked_amount = 0.0
        
        if load_existing and name:
            # 加载已存在的钱包
            self.name = name
            self._load_wallet()
        else:
            # 创建新钱包
            self.name = name if name else f"wallet_{uuid.uuid4().hex[:8]}"
            self._generate_keys()
            self._save_wallet()
        
        # 初始化交易历史
        self.transaction_history = []
        
        # 初始化账单管理器
        self.bill_manager = BillManager()
        
        # # 初始化质押信息
        # self.staked_amount = 0.0
    
    def _generate_keys(self) -> None:
        """生成新的密钥对"""
        # 生成私钥
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # 从私钥获取公钥
        self.public_key = self.private_key.public_key()
        
        # 生成钱包地址（使用公钥的哈希）
        self.address = self._generate_address()
        
        print(f"生成新钱包: {self.name}, 地址: {self.address}")
    
    def _generate_address(self) -> str:
        """
        从公钥生成钱包地址
        
        Returns:
            str: 钱包地址
        """
        # 序列化公钥
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # 计算公钥的哈希
        address_hash = hashlib.sha256(public_bytes).hexdigest()
        
        # 返回地址（使用前20个字节，添加前缀）
        return f"WALLET_{address_hash[:20]}"
    
    def _save_wallet(self) -> None:
        """保存钱包到文件"""
        # 序列化私钥
        private_bytes = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # 序列化公钥
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # 创建钱包数据
        wallet_data = {
            'name': self.name,
            'address': self.address,
            'private_key': base64.b64encode(private_bytes).decode('utf-8'),
            'public_key': base64.b64encode(public_bytes).decode('utf-8'),
            'staked_amount': self.staked_amount
        }
        
        # 保存到文件
        wallet_path = os.path.join(self.wallet_dir, f"{self.name}.json")
        with open(wallet_path, 'w') as f:
            json.dump(wallet_data, f, indent=4)
        
        print(f"钱包已保存到: {wallet_path}")
    
    def _load_wallet(self) -> None:
        """从文件加载钱包"""
        wallet_path = os.path.join(self.wallet_dir, f"{self.name}.json")
        
        try:
            with open(wallet_path, 'r') as f:
                wallet_data = json.load(f)
            
            # 加载钱包数据
            self.name = wallet_data['name']
            self.address = wallet_data['address']
            
            # 加载私钥
            private_bytes = base64.b64decode(wallet_data['private_key'])
            self.private_key = serialization.load_pem_private_key(
                private_bytes,
                password=None
            )
            
            # 加载公钥
            public_bytes = base64.b64decode(wallet_data['public_key'])
            self.public_key = serialization.load_pem_public_key(public_bytes)
            
            # 加载质押金额（如果存在）
            self.staked_amount = wallet_data.get('staked_amount', 0.0)
            
            print(f"已加载钱包: {self.name}, 地址: {self.address}")
        except Exception as e:
            raise Exception(f"加载钱包失败: {e}")
    
    def sign_transaction(self, transaction: Transaction) -> None:
        """
        签名交易
        
        Args:
            transaction: 要签名的交易
        """
        # 确保交易发送方是当前钱包
        if transaction.sender != self.address:
            raise ValueError(f"交易发送方 {transaction.sender} 与钱包地址 {self.address} 不匹配")
        
        # 准备要签名的数据
        transaction_data = f"{transaction.sender}:{transaction.recipient}:{transaction.amount}:{transaction.fee}:{transaction.timestamp}:{transaction.transaction_id}"
        
        # 签名
        signature = self.private_key.sign(
            transaction_data.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # 将签名添加到交易
        transaction.sign_transaction(base64.b64encode(signature).decode('utf-8'))
    
    def verify_transaction(self, transaction: Transaction, public_key_pem: str) -> bool:
        """
        验证交易签名
        
        Args:
            transaction: 要验证的交易
            public_key_pem: 发送方的公钥（PEM格式）
            
        Returns:
            bool: 签名是否有效
        """
        if not transaction.signature:
            return False
        
        try:
            # 加载公钥
            public_key = serialization.load_pem_public_key(
                base64.b64decode(public_key_pem)
            )
            
            # 准备要验证的数据
            transaction_data = f"{transaction.sender}:{transaction.recipient}:{transaction.amount}:{transaction.fee}:{transaction.timestamp}:{transaction.transaction_id}"
            
            # 解码签名
            signature = base64.b64decode(transaction.signature)
            
            # 验证签名
            public_key.verify(
                signature,
                transaction_data.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            print(f"验证交易签名时出错: {e}")
            return False
    
    def create_transaction(self, recipient: str, amount: float, fee: float = 0.001, node=None) -> Transaction:
        """
        创建交易
        
        Args:
            recipient: 接收方地址
            amount: 交易金额
            fee: 交易费用
            node: 节点实例（可选，用于直接添加交易到区块链）
            
        Returns:
            Transaction: 创建的交易
        """
        if amount <= 0:
            raise ValueError("交易金额必须大于0")
        
        # 创建交易
        transaction = Transaction(
            sender=self.address,
            recipient=recipient,
            amount=amount,
            fee=fee
        )
        
        # 签名交易
        self.sign_transaction(transaction)
        
        # 添加到交易历史
        self.transaction_history.append(transaction)
        
        # 如果提供了节点，将交易添加到区块链
        if node:
            if node.blockchain.add_transaction(transaction):
                # 广播交易
                node.p2p_node.broadcast_new_transaction(transaction)
                print(f"交易已添加到区块链并广播: {transaction.transaction_id}")
            else:
                print(f"添加交易到区块链失败: {transaction.transaction_id}")
        
        return transaction
    
    def create_bill(self, payee: str, amount: float, description: str) -> Bill:
        """
        创建账单
        
        Args:
            payee: 收款方地址
            amount: 金额
            description: 描述
            
        Returns:
            Bill: 创建的账单
        """
        bill = self.bill_manager.create_bill(self.address, payee, amount, description)
        print(f"创建账单: {bill.bill_id}, 金额: {amount}, 收款方: {payee}")
        return bill
    
    def pay_bill(self, bill: Bill, node=None) -> Optional[Transaction]:
        """
        支付账单
        
        Args:
            bill: 账单
            node: 节点实例（可选，用于直接添加交易到区块链）
            
        Returns:
            Optional[Transaction]: 创建的交易，如果支付失败则返回None
        """
        # 验证账单
        if not self.bill_manager.verify_bill(bill):
            print(f"账单验证失败: {bill.bill_id}")
            return None
        
        # 检查账单付款方是否为当前钱包
        if bill.payer != self.address:
            print(f"账单付款方 {bill.payer} 与钱包地址 {self.address} 不匹配")
            return None
        
        # 创建交易
        try:
            transaction = self.create_transaction(
                recipient=bill.payee,
                amount=bill.amount,
                node=node
            )
            print(f"支付账单成功: {bill.bill_id}, 交易ID: {transaction.transaction_id}")
            return transaction
        except Exception as e:
            print(f"支付账单失败: {e}")
            return None
    
    def get_transaction_history(self) -> List[Dict[str, Any]]:
        """
        获取交易历史
        
        Returns:
            List[Dict[str, Any]]: 交易历史列表
        """
        return [tx.to_dict() for tx in self.transaction_history]
    
    def export_public_key(self) -> str:
        """
        导出公钥
        
        Returns:
            str: 公钥（PEM格式，Base64编码）
        """
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(public_bytes).decode('utf-8')
    
    def get_balance(self, node) -> float:
        """
        获取钱包余额
        
        Args:
            node: 节点实例
            
        Returns:
            float: 钱包余额
        """
        balance = 0.0
        
        # 遍历区块链中的所有交易
        for block in node.blockchain.chain:
            for tx in block.transactions:
                # 如果是收款方，增加余额
                if tx.recipient == self.address:
                    balance += tx.amount
                
                # 如果是付款方，减少余额和手续费
                if tx.sender == self.address:
                    balance -= (tx.amount + tx.fee)
        
        # 考虑待处理交易
        for tx in node.blockchain.pending_transactions:
            # 如果是收款方，增加余额
            if tx.recipient == self.address:
                balance += tx.amount
            
            # 如果是付款方，减少余额和手续费
            if tx.sender == self.address:
                balance -= (tx.amount + tx.fee)
        
        # 减去已质押的金额
        balance -= self.staked_amount
        
        return balance
    
    def stake_tokens(self, amount: float, node) -> bool:
        """
        质押代币
        
        Args:
            amount: 质押金额
            node: 节点实例
            
        Returns:
            bool: 质押是否成功
        """
        if amount <= 0:
            print("质押金额必须大于0")
            return False
        
        # 检查余额
        available_balance = self.get_balance(node)
        if available_balance < amount:
            print(f"可用余额不足: {available_balance} < {amount}")
            return False
        
        # 设置节点ID为钱包地址
        node.node_id = self.address
        
        # 质押代币
        if node.stake(amount):
            # 更新钱包的质押金额
            self.staked_amount += amount
            # 保存钱包
            self._save_wallet()
            print(f"已质押 {amount} 代币，总质押: {self.staked_amount}")
            return True
        else:
            print("质押失败")
            return False
    
    def unstake_tokens(self, amount: float, node) -> bool:
        """
        取消质押
        
        Args:
            amount: 取消质押的金额
            node: 节点实例
            
        Returns:
            bool: 取消质押是否成功
        """
        if amount <= 0:
            print("取消质押金额必须大于0")
            return False
        
        if amount > self.staked_amount:
            print(f"质押金额不足: {self.staked_amount} < {amount}")
            return False
        
        # 设置节点ID为钱包地址
        node.node_id = self.address
        
        # 取消质押
        if node.unstake(amount):
            # 更新钱包的质押金额
            self.staked_amount -= amount
            # 保存钱包
            self._save_wallet()
            print(f"已取消质押 {amount} 代币，剩余质押: {self.staked_amount}")
            return True
        else:
            print("取消质押失败")
            return False
    
    def get_staked_amount(self) -> float:
        """
        获取质押金额
        
        Returns:
            float: 质押金额
        """
        return self.staked_amount
    
    def get_validator_info(self, node) -> Optional[Dict]:
        """
        获取验证者信息
        
        Args:
            node: 节点实例
            
        Returns:
            Optional[Dict]: 验证者信息，如果不是验证者则返回None
        """
        validators = node.get_validator_info()
        for validator in validators:
            if validator['address'] == self.address:
                return validator
        return None


class WalletManager:
    """钱包管理器类，管理多个钱包"""
    
    def __init__(self, wallet_dir: str = "wallets"):
        """
        初始化钱包管理器
        
        Args:
            wallet_dir: 钱包文件存储目录
        """
        self.wallet_dir = wallet_dir
        self.wallets = {}  # 名称 -> 钱包对象
        
        # 创建钱包目录
        os.makedirs(wallet_dir, exist_ok=True)
        
        # 加载已存在的钱包
        self._load_wallets()
    
    def _load_wallets(self) -> None:
        """加载所有已存在的钱包"""
        wallet_files = [f for f in os.listdir(self.wallet_dir) if f.endswith('.json')]
        
        for wallet_file in wallet_files:
            wallet_name = wallet_file.replace('.json', '')
            try:
                wallet = Wallet(name=wallet_name, load_existing=True, wallet_dir=self.wallet_dir)
                self.wallets[wallet_name] = wallet
            except Exception as e:
                print(f"加载钱包 {wallet_name} 失败: {e}")
    
    def create_wallet(self, name: str = None) -> Wallet:
        """
        创建新钱包
        
        Args:
            name: 钱包名称，如果为None则自动生成
            
        Returns:
            Wallet: 创建的钱包
        """
        if name and name in self.wallets:
            raise ValueError(f"钱包 {name} 已存在")
        
        wallet = Wallet(name=name, wallet_dir=self.wallet_dir)
        self.wallets[wallet.name] = wallet
        
        return wallet
    
    def get_wallet(self, name: str) -> Optional[Wallet]:
        """
        获取钱包
        
        Args:
            name: 钱包名称
            
        Returns:
            Optional[Wallet]: 钱包对象，如果不存在则返回None
        """
        return self.wallets.get(name)
    
    def get_wallet_by_address(self, address: str) -> Optional[Wallet]:
        """
        通过地址获取钱包
        
        Args:
            address: 钱包地址
            
        Returns:
            Optional[Wallet]: 钱包对象，如果不存在则返回None
        """
        for wallet in self.wallets.values():
            if wallet.address == address:
                return wallet
        return None
    
    def list_wallets(self) -> List[Dict[str, str]]:
        """
        列出所有钱包
        
        Returns:
            List[Dict[str, str]]: 钱包信息列表
        """
        return [{'name': wallet.name, 'address': wallet.address} for wallet in self.wallets.values()]
    
    def delete_wallet(self, name: str) -> bool:
        """
        删除钱包
        
        Args:
            name: 钱包名称
            
        Returns:
            bool: 是否成功删除
        """
        if name not in self.wallets:
            return False
        
        # 删除钱包文件
        wallet_path = os.path.join(self.wallet_dir, f"{name}.json")
        try:
            os.remove(wallet_path)
            # 从管理器中移除钱包
            del self.wallets[name]
            return True
        except Exception as e:
            print(f"删除钱包 {name} 失败: {e}")
            return False