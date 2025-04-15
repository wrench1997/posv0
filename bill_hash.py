# bill_hash.py

import hashlib
import json
import time
from typing import Dict, List, Any, Optional
import uuid

class Bill:
    """账单类"""
    
    def __init__(self, bill_id: str, payer: str, payee: str, amount: float, description: str):
        """
        初始化账单
        
        Args:
            bill_id: 账单ID
            payer: 付款方
            payee: 收款方
            amount: 金额
            description: 描述
        """
        self.bill_id = bill_id
        self.payer = payer
        self.payee = payee
        self.amount = amount
        self.description = description
        self.timestamp = time.time()
        self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """
        计算账单哈希
        
        Returns:
            str: 账单哈希值
        """
        bill_dict = {
            'bill_id': self.bill_id,
            'payer': self.payer,
            'payee': self.payee,
            'amount': self.amount,
            'description': self.description,
            'timestamp': self.timestamp
        }
        
        bill_string = json.dumps(bill_dict, sort_keys=True)
        return hashlib.sha256(bill_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将账单转换为字典格式
        
        Returns:
            Dict[str, Any]: 账单字典
        """
        return {
            'bill_id': self.bill_id,
            'payer': self.payer,
            'payee': self.payee,
            'amount': self.amount,
            'description': self.description,
            'timestamp': self.timestamp,
            'hash': self.hash
        }
    
    @classmethod
    def from_dict(cls, bill_dict: Dict[str, Any]) -> 'Bill':
        """
        从字典创建账单对象
        
        Args:
            bill_dict: 账单字典
            
        Returns:
            Bill: 账单对象
        """
        bill = cls(
            bill_id=bill_dict['bill_id'],
            payer=bill_dict['payer'],
            payee=bill_dict['payee'],
            amount=bill_dict['amount'],
            description=bill_dict['description']
        )
        bill.timestamp = bill_dict['timestamp']
        bill.hash = bill_dict['hash']
        return bill


class BillManager:
    """账单管理器类"""
    
    def __init__(self):
        """初始化账单管理器"""
        self.bills: Dict[str, Bill] = {}  # 账单ID -> 账单对象
        self.bill_hashes: Dict[str, str] = {}  # 账单哈希 -> 账单ID
    
    def create_bill(self, payer: str, payee: str, amount: float, description: str) -> Bill:
        """
        创建账单
        
        Args:
            payer: 付款方
            payee: 收款方
            amount: 金额
            description: 描述
            
        Returns:
            Bill: 创建的账单
        """
        bill_id = str(uuid.uuid4())
        bill = Bill(bill_id, payer, payee, amount, description)
        
        # 存储账单
        self.bills[bill_id] = bill
        self.bill_hashes[bill.hash] = bill_id
        
        print(f"创建账单: {bill_id}, 哈希: {bill.hash}")
        
        return bill
    
    def get_bill(self, bill_id: str) -> Optional[Bill]:
        """
        获取账单
        
        Args:
            bill_id: 账单ID
            
        Returns:
            Optional[Bill]: 账单对象，如果不存在则返回None
        """
        return self.bills.get(bill_id)
    
    def get_bill_by_hash(self, bill_hash: str) -> Optional[Bill]:
        """
        通过哈希获取账单
        
        Args:
            bill_hash: 账单哈希
            
        Returns:
            Optional[Bill]: 账单对象，如果不存在则返回None
        """
        bill_id = self.bill_hashes.get(bill_hash)
        if bill_id:
            return self.bills.get(bill_id)
        return None
    
    def verify_bill(self, bill: Bill) -> bool:
        """
        验证账单
        
        Args:
            bill: 账单对象
            
        Returns:
            bool: 账单是否有效
        """
        return bill.hash == bill.calculate_hash()
    
    def bill_to_transaction(self, bill: Bill) -> Dict[str, Any]:
        """
        将账单转换为交易数据
        
        Args:
            bill: 账单对象
            
        Returns:
            Dict[str, Any]: 交易数据
        """
        return {
            'sender': bill.payer,
            'recipient': bill.payee,
            'amount': bill.amount,
            'fee': 0.001,  # 默认交易费用
            'bill_hash': bill.hash,
            'description': bill.description
        }
