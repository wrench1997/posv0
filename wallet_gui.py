# wallet_gui.py

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
import sys
from typing import Dict, List, Any, Optional

from wallet import WalletManager, Wallet
from main import Node

class WalletGUI:
    """钱包图形用户界面"""
    
    def __init__(self, root):
        """
        初始化钱包GUI
        
        Args:
            root: tkinter根窗口
        """
        self.root = root
        self.root.title("区块链钱包")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # 初始化钱包管理器
        self.wallet_manager = WalletManager()
        self.current_wallet = None
        self.node = None
        
        # 创建UI组件
        self.create_widgets()
        
        # 更新钱包列表
        self.update_wallet_list()
        
        # 启动自动更新线程
        self.running = True
        threading.Thread(target=self.auto_update, daemon=True).start()
    
    def create_widgets(self):
        """创建UI组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建左侧面板（钱包列表和节点控制）
        left_frame = ttk.LabelFrame(main_frame, text="钱包和节点", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建右侧面板（交易和账单）
        right_frame = ttk.LabelFrame(main_frame, text="交易和账单", padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧面板内容
        # 钱包列表
        wallet_frame = ttk.LabelFrame(left_frame, text="钱包列表", padding=10)
        wallet_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 钱包列表视图
        self.wallet_tree = ttk.Treeview(wallet_frame, columns=("name", "address"), show="headings")
        self.wallet_tree.heading("name", text="名称")
        self.wallet_tree.heading("address", text="地址")
        self.wallet_tree.column("name", width=100)
        self.wallet_tree.column("address", width=200)
        self.wallet_tree.pack(fill=tk.BOTH, expand=True)
        self.wallet_tree.bind("<Double-1>", self.on_wallet_select)
        
        # 钱包操作按钮
        wallet_btn_frame = ttk.Frame(wallet_frame)
        wallet_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(wallet_btn_frame, text="创建钱包", command=self.create_wallet).pack(side=tk.LEFT, padx=5)
        ttk.Button(wallet_btn_frame, text="刷新列表", command=self.update_wallet_list).pack(side=tk.LEFT, padx=5)
        
        # 节点控制
        node_frame = ttk.LabelFrame(left_frame, text="节点控制", padding=10)
        node_frame.pack(fill=tk.BOTH, pady=5)
        
        # 节点状态
        self.node_status_var = tk.StringVar(value="节点未启动")
        ttk.Label(node_frame, textvariable=self.node_status_var).pack(fill=tk.X, pady=5)
        
        # 节点操作按钮
        node_btn_frame = ttk.Frame(node_frame)
        node_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(node_btn_frame, text="启动节点", command=self.start_node).pack(side=tk.LEFT, padx=5)
        ttk.Button(node_btn_frame, text="连接网络", command=self.connect_to_network).pack(side=tk.LEFT, padx=5)
        
        # 区块链信息
        blockchain_frame = ttk.LabelFrame(left_frame, text="区块链信息", padding=10)
        blockchain_frame.pack(fill=tk.BOTH, pady=5)
        
        # 区块链状态
        self.blockchain_info_var = tk.StringVar(value="未连接到区块链")
        ttk.Label(blockchain_frame, textvariable=self.blockchain_info_var).pack(fill=tk.X, pady=5)
        
        # 质押控制
        stake_frame = ttk.LabelFrame(left_frame, text="质押控制", padding=10)
        stake_frame.pack(fill=tk.BOTH, pady=5)
        
        # 质押状态
        self.stake_info_var = tk.StringVar(value="未质押")
        ttk.Label(stake_frame, textvariable=self.stake_info_var).pack(fill=tk.X, pady=5)
        
        # 质押操作按钮
        stake_btn_frame = ttk.Frame(stake_frame)
        stake_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(stake_btn_frame, text="质押代币", command=self.stake_tokens).pack(side=tk.LEFT, padx=5)
        ttk.Button(stake_btn_frame, text="取消质押", command=self.unstake_tokens).pack(side=tk.LEFT, padx=5)
        
        # 右侧面板内容
        # 当前钱包信息
        wallet_info_frame = ttk.LabelFrame(right_frame, text="当前钱包", padding=10)
        wallet_info_frame.pack(fill=tk.X, pady=5)
        
        self.current_wallet_var = tk.StringVar(value="未选择钱包")
        ttk.Label(wallet_info_frame, textvariable=self.current_wallet_var).pack(fill=tk.X, pady=5)
        
        self.balance_var = tk.StringVar(value="余额: 0.0")
        ttk.Label(wallet_info_frame, textvariable=self.balance_var).pack(fill=tk.X, pady=5)
        
        # 交易操作
        transaction_frame = ttk.LabelFrame(right_frame, text="创建交易", padding=10)
        transaction_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(transaction_frame, text="接收方地址:").pack(anchor=tk.W, pady=2)
        self.recipient_entry = ttk.Entry(transaction_frame, width=50)
        self.recipient_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(transaction_frame, text="金额:").pack(anchor=tk.W, pady=2)
        self.amount_entry = ttk.Entry(transaction_frame)
        self.amount_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(transaction_frame, text="费用:").pack(anchor=tk.W, pady=2)
        self.fee_entry = ttk.Entry(transaction_frame)
        self.fee_entry.insert(0, "0.001")
        self.fee_entry.pack(fill=tk.X, pady=2)
        
        ttk.Button(transaction_frame, text="创建交易", command=self.create_transaction).pack(anchor=tk.E, pady=5)
        
        # 账单操作
        bill_frame = ttk.LabelFrame(right_frame, text="账单操作", padding=10)
        bill_frame.pack(fill=tk.X, pady=5)
        
        bill_btn_frame = ttk.Frame(bill_frame)
        bill_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(bill_btn_frame, text="创建账单", command=self.create_bill).pack(side=tk.LEFT, padx=5)
        ttk.Button(bill_btn_frame, text="支付账单", command=self.pay_bill).pack(side=tk.LEFT, padx=5)
        
        # 交易历史
        history_frame = ttk.LabelFrame(right_frame, text="交易历史", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 交易历史列表
        self.history_tree = ttk.Treeview(history_frame, columns=("id", "type", "amount", "time"), show="headings")
        self.history_tree.heading("id", text="交易ID")
        self.history_tree.heading("type", text="类型")
        self.history_tree.heading("amount", text="金额")
        self.history_tree.heading("time", text="时间")
        self.history_tree.column("id", width=100)
        self.history_tree.column("type", width=50)
        self.history_tree.column("amount", width=80)
        self.history_tree.column("time", width=150)
        self.history_tree.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def update_wallet_list(self):
        """更新钱包列表"""
        # 清空列表
        for item in self.wallet_tree.get_children():
            self.wallet_tree.delete(item)
        
        # 添加钱包
        wallets = self.wallet_manager.list_wallets()
        for wallet in wallets:
            self.wallet_tree.insert("", tk.END, values=(wallet['name'], wallet['address']))
        
        self.status_var.set(f"找到 {len(wallets)} 个钱包")
    
    def on_wallet_select(self, event):
        """
        处理钱包选择事件
        
        Args:
            event: 事件对象
        """
        selected_item = self.wallet_tree.selection()
        if not selected_item:
            return
        
        wallet_name = self.wallet_tree.item(selected_item[0], "values")[0]
        self.select_wallet(wallet_name)
    
    def select_wallet(self, name):
        """
        选择钱包
        
        Args:
            name: 钱包名称
        """
        wallet = self.wallet_manager.get_wallet(name)
        
        if wallet:
            self.current_wallet = wallet
            self.current_wallet_var.set(f"当前钱包: {wallet.name}\n地址: {wallet.address}")
            self.update_balance()
            self.update_transaction_history()
            self.status_var.set(f"已选择钱包: {wallet.name}")
        else:
            messagebox.showerror("错误", f"钱包 {name} 不存在")
    
    def create_wallet(self):
        """创建新钱包"""
        name = simpledialog.askstring("创建钱包", "请输入钱包名称 (留空自动生成):")
        
        try:
            wallet = self.wallet_manager.create_wallet(name)
            self.update_wallet_list()
            self.select_wallet(wallet.name)
            messagebox.showinfo("成功", f"已创建钱包: {wallet.name}")
        except Exception as e:
            messagebox.showerror("错误", f"创建钱包失败: {e}")
    
    def start_node(self):
        """启动本地节点"""
        if self.node:
            messagebox.showinfo("提示", "节点已经在运行")
            return
        
        host = simpledialog.askstring("启动节点", "请输入主机地址:", initialvalue="127.0.0.1")
        if not host:
            return
        
        port = simpledialog.askinteger("启动节点", "请输入端口号:", initialvalue=5000)
        if not port:
            return
        
        node_id = f"Node_GUI_{port}"
        self.node = Node(node_id, host, port)
        self.node.start()
        
        self.node_status_var.set(f"节点已启动: {node_id}\n地址: {host}:{port}")
        self.status_var.set(f"本地节点 {node_id} 已启动")
        
        # 更新区块链信息
        self.update_blockchain_info()
    
    def connect_to_network(self):
        """连接到网络"""
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        seed_host = simpledialog.askstring("连接网络", "请输入种子节点主机地址:")
        if not seed_host:
            return
        
        seed_port = simpledialog.askinteger("连接网络", "请输入种子节点端口号:")
        if not seed_port:
            return
        
        if self.node.connect_to_network(seed_host, seed_port):
            messagebox.showinfo("成功", f"已连接到网络节点 {seed_host}:{seed_port}")
            self.status_var.set(f"已连接到网络节点 {seed_host}:{seed_port}")
        else:
            messagebox.showerror("错误", f"连接到网络节点 {seed_host}:{seed_port} 失败")
    
    def update_balance(self):
        """更新余额显示"""
        if not self.current_wallet or not self.node:
            return
        
        balance = self.current_wallet.get_balance(self.node)
        self.balance_var.set(f"余额: {balance}")
    
    def update_blockchain_info(self):
        """更新区块链信息"""
        if not self.node:
            return
        
        info = self.node.get_blockchain_info()
        self.blockchain_info_var.set(
            f"链长度: {info['chain_length']}\n"
            f"待处理交易: {info['pending_transactions']}\n"
            f"链是否有效: {info['is_valid']}"
        )
        
        # 更新质押信息
        self.stake_info_var.set(
            f"质押金额: {self.node.get_staked_amount()}\n"
            f"可用余额: {self.node.get_balance()}"
        )
    
    def update_transaction_history(self):
        """更新交易历史"""
        if not self.current_wallet:
            return
        
        # 清空列表
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # 获取交易历史
        history = self.current_wallet.get_transaction_history()
        
        # 添加交易记录
        for tx in history:
            tx_type = "发送" if tx['sender'] == self.current_wallet.address else "接收"
            amount = tx['amount']
            if tx_type == "发送":
                amount = -amount
            
            # 格式化时间
            tx_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tx['timestamp']))
            
            self.history_tree.insert("", tk.END, values=(
                tx['transaction_id'][:8] + "...",
                tx_type,
                amount,
                tx_time
            ))
    
    def create_transaction(self):
        """创建交易"""
        if not self.current_wallet:
            messagebox.showerror("错误", "请先选择钱包")
            return
        
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        recipient = self.recipient_entry.get().strip()
        if not recipient:
            messagebox.showerror("错误", "请输入接收方地址")
            return
        
        try:
            amount = float(self.amount_entry.get())
            fee = float(self.fee_entry.get())
        except ValueError:
            messagebox.showerror("错误", "金额和费用必须是数字")
            return
        
        if amount <= 0:
            messagebox.showerror("错误", "交易金额必须大于0")
            return
        
        # 检查余额
        balance = self.current_wallet.get_balance(self.node)
        total_amount = amount + fee
        
        if balance < total_amount:
            messagebox.showerror("错误", f"余额不足: {balance} < {total_amount}")
            return
        
        try:
            # 创建交易
            transaction = self.current_wallet.create_transaction(
                recipient=recipient,
                amount=amount,
                fee=fee,
                node=self.node
            )
            
            messagebox.showinfo("成功", f"交易已创建: {transaction.transaction_id}")
            self.status_var.set(f"交易已创建: {transaction.transaction_id}")
            
            # 清空输入框
            self.recipient_entry.delete(0, tk.END)
            self.amount_entry.delete(0, tk.END)
            
            # 更新余额和交易历史
            self.update_balance()
            self.update_transaction_history()
        except Exception as e:
            messagebox.showerror("错误", f"创建交易失败: {e}")
    
    def create_bill(self):
        """创建账单"""
        if not self.current_wallet:
            messagebox.showerror("错误", "请先选择钱包")
            return
        
        payee = simpledialog.askstring("创建账单", "请输入收款方地址:")
        if not payee:
            return
        
        amount = simpledialog.askfloat("创建账单", "请输入金额:")
        if not amount or amount <= 0:
            messagebox.showerror("错误", "金额必须大于0")
            return
        
        description = simpledialog.askstring("创建账单", "请输入描述:")
        if not description:
            return
        
        try:
            bill = self.current_wallet.create_bill(payee, amount, description)
            messagebox.showinfo("成功", f"账单已创建: {bill.bill_id}")
            self.status_var.set(f"账单已创建: {bill.bill_id}")
        except Exception as e:
            messagebox.showerror("错误", f"创建账单失败: {e}")
    
    def pay_bill(self):
        """支付账单"""
        if not self.current_wallet:
            messagebox.showerror("错误", "请先选择钱包")
            return
        
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        bill_id = simpledialog.askstring("支付账单", "请输入账单ID:")
        if not bill_id:
            return
        
        # 获取账单
        bill = self.current_wallet.bill_manager.get_bill(bill_id)
        
        if not bill:
            messagebox.showerror("错误", f"账单 {bill_id} 不存在")
            return
        
        # 支付账单
        transaction = self.current_wallet.pay_bill(bill, self.node)
        
        if transaction:
            messagebox.showinfo("成功", f"账单 {bill_id} 已支付，交易ID: {transaction.transaction_id}")
            self.status_var.set(f"账单 {bill_id} 已支付")
            
            # 更新余额和交易历史
            self.update_balance()
            self.update_transaction_history()
        else:
            messagebox.showerror("错误", f"支付账单 {bill_id} 失败")
    
    def stake_tokens(self):
        """质押代币"""
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        amount = simpledialog.askfloat("质押代币", "请输入质押金额:")
        if not amount or amount <= 0:
            messagebox.showerror("错误", "质押金额必须大于0")
            return
        
        # 检查余额
        balance = self.node.get_balance()
        
        if balance < amount:
            messagebox.showerror("错误", f"余额不足: {balance} < {amount}")
            return
        
        # 质押代币
        if self.node.stake(amount):
            messagebox.showinfo("成功", f"已质押 {amount} 代币")
            self.status_var.set(f"已质押 {amount} 代币")
            
            # 更新质押信息
            self.update_blockchain_info()
        else:
            messagebox.showerror("错误", f"质押代币失败")
    
    def unstake_tokens(self):
        """取消质押"""
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        staked_amount = self.node.get_staked_amount()
        if staked_amount <= 0:
            messagebox.showerror("错误", "没有质押的代币")
            return
        
        amount = simpledialog.askfloat("取消质押", f"请输入取消质押的金额 (最大 {staked_amount}):")
        if not amount or amount <= 0:
            messagebox.showerror("错误", "取消质押的金额必须大于0")
            return
        
        if amount > staked_amount:
            messagebox.showerror("错误", f"取消质押的金额不能超过已质押金额: {staked_amount}")
            return
        
        # 取消质押
        if self.node.unstake(amount):
            messagebox.showinfo("成功", f"已取消质押 {amount} 代币")
            self.status_var.set(f"已取消质押 {amount} 代币")
            
            # 更新质押信息
            self.update_blockchain_info()
        else:
            messagebox.showerror("错误", f"取消质押失败")
    
    def auto_update(self):
        """自动更新UI信息"""
        while self.running:
            if self.node:
                self.update_blockchain_info()
            
            if self.current_wallet and self.node:
                self.update_balance()
            
            time.sleep(5)
    
    def on_closing(self):
        """窗口关闭事件处理"""
        self.running = False
        if self.node:
            self.node.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = WalletGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()