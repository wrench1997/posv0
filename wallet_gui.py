# wallet_gui.py

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading
import time
import sys
import json
import os
from typing import Dict, List, Any, Optional

from wallet import WalletManager, Wallet
from main import Node
from mining_rewards import RewardCalculator, RewardDistributor
from pos_consensus import POSConsensus
from bill_hash import BillManager

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
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        # 初始化钱包管理器
        self.wallet_manager = WalletManager()
        self.current_wallet = None
        self.node = None
        self.data_dir = "blockchain_data"
        
        # 创建数据目录
        os.makedirs(self.data_dir, exist_ok=True)
        
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
        ttk.Button(wallet_btn_frame, text="导出钱包", command=self.export_wallet).pack(side=tk.LEFT, padx=5)
        ttk.Button(wallet_btn_frame, text="导入钱包", command=self.import_wallet).pack(side=tk.LEFT, padx=5)
        
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
        ttk.Button(node_btn_frame, text="查看网络", command=self.show_network_info).pack(side=tk.LEFT, padx=5)
        
        # 区块链信息
        blockchain_frame = ttk.LabelFrame(left_frame, text="区块链信息", padding=10)
        blockchain_frame.pack(fill=tk.BOTH, pady=5)
        
        # 区块链状态
        self.blockchain_info_var = tk.StringVar(value="未连接到区块链")
        ttk.Label(blockchain_frame, textvariable=self.blockchain_info_var).pack(fill=tk.X, pady=5)
        
        # 区块链操作按钮
        blockchain_btn_frame = ttk.Frame(blockchain_frame)
        blockchain_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(blockchain_btn_frame, text="查看详情", command=self.show_blockchain_details).pack(side=tk.LEFT, padx=5)
        
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
        ttk.Button(stake_btn_frame, text="验证者信息", command=self.show_validator_info).pack(side=tk.LEFT, padx=5)
        
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
        ttk.Button(bill_btn_frame, text="查看账单", command=self.show_bills).pack(side=tk.LEFT, padx=5)
        
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
        
        # 添加滚动条
        history_scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_tree.yview)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        
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
            
            # 如果节点已启动，更新节点ID
            if self.node:
                self.node.node_id = wallet.address
                
                # 同步质押状态
                if wallet.staked_amount > 0:
                    self.node.staked_amount = wallet.staked_amount
                    self.node.pos_consensus.add_stake(wallet.address, wallet.staked_amount)
                
                self.update_balance()
                self.update_transaction_history()
                self.update_stake_info()
            
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
    
    def export_wallet(self):
        """导出钱包"""
        if not self.current_wallet:
            messagebox.showerror("错误", "请先选择钱包")
            return
        
        export_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")],
            initialfile=f"{self.current_wallet.name}_exported.json"
        )
        
        if not export_path:
            return
        
        try:
            # 复制钱包文件
            wallet_path = os.path.join(self.current_wallet.wallet_dir, f"{self.current_wallet.name}.json")
            with open(wallet_path, 'r') as src, open(export_path, 'w') as dst:
                dst.write(src.read())
            
            messagebox.showinfo("成功", f"钱包已导出到: {export_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出钱包失败: {e}")
    
    def import_wallet(self):
        """导入钱包"""
        import_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")]
        )
        
        if not import_path:
            return
        
        try:
            # 读取导入文件
            with open(import_path, 'r') as f:
                wallet_data = json.loads(f.read())
            
            # 获取钱包名称
            name = wallet_data.get('name')
            
            if not name:
                messagebox.showerror("错误", "导入文件中没有钱包名称")
                return
            
            # 检查钱包是否已存在
            if name in self.wallet_manager.wallets:
                messagebox.showerror("错误", f"钱包 {name} 已存在，请先删除或重命名")
                return
            
            # 复制钱包文件
            wallet_path = os.path.join(self.wallet_manager.wallet_dir, f"{name}.json")
            with open(import_path, 'r') as src, open(wallet_path, 'w') as dst:
                dst.write(src.read())
            
            # 重新加载钱包
            self.wallet_manager._load_wallets()
            
            messagebox.showinfo("成功", f"钱包 {name} 已导入")
            
            # 更新钱包列表
            self.update_wallet_list()
            
            # 选择导入的钱包
            self.select_wallet(name)
        except Exception as e:
            messagebox.showerror("错误", f"导入钱包失败: {e}")
    
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
        
        # 使用当前钱包地址作为节点ID
        node_id = self.current_wallet.address if self.current_wallet else f"Node_GUI_{port}"
        
        self.node = Node(node_id, host, port)
        self.node.start()
        
        # 如果有当前钱包，设置节点的余额为钱包余额
        if self.current_wallet:
            # 同步质押状态
            if self.current_wallet.staked_amount > 0:
                self.node.staked_amount = self.current_wallet.staked_amount
                self.node.pos_consensus.add_stake(self.current_wallet.address, self.current_wallet.staked_amount)
        
        self.node_status_var.set(f"节点已启动: {node_id}\n地址: {host}:{port}")
        self.status_var.set(f"本地节点 {node_id} 已启动")
        
        # 更新区块链信息
        self.update_blockchain_info()
        
        # 如果有当前钱包，更新余额
        if self.current_wallet:
            self.update_balance()
            self.update_transaction_history()
            self.update_stake_info()
    
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
            
            # 连接成功后自动发现其他节点
            self.node.auto_discover_nodes()
            
            # 同步区块链
            self.node.p2p_node.synchronize_blockchain()
            
            # 更新区块链信息
            self.update_blockchain_info()
        else:
            messagebox.showerror("错误", f"连接到网络节点 {seed_host}:{seed_port} 失败")
    
    def show_network_info(self):
        """显示网络信息"""
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        peers = self.node.p2p_node.peers
        
        info = f"本地节点: {self.node.node_id} ({self.node.host}:{self.node.port})\n"
        info += f"已连接节点数: {len(peers)}\n\n"
        
        if peers:
            info += "已连接节点:\n"
            for i, (peer_id, (host, port)) in enumerate(peers.items()):
                info += f"{i+1}. {peer_id} ({host}:{port})\n"
        
        # 创建对话框显示网络信息
        network_dialog = tk.Toplevel(self.root)
        network_dialog.title("网络信息")
        network_dialog.geometry("500x400")
        
        # 添加文本框
        text = tk.Text(network_dialog, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(text, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scrollbar.set)
        
        # 插入信息
        text.insert(tk.END, info)
        text.config(state=tk.DISABLED)  # 设置为只读
    
    def update_balance(self):
        """更新余额显示"""
        if not self.current_wallet or not self.node:
            return
        
        balance = self.current_wallet.get_balance(self.node)
        staked = self.current_wallet.get_staked_amount()
        total = balance + staked
        
        self.balance_var.set(
            f"可用余额: {balance}\n"
            f"质押金额: {staked}\n"
            f"总资产: {total}"
        )
    
    def update_blockchain_info(self):
        """更新区块链信息"""
        if not self.node:
            return
        
        info = self.node.get_blockchain_info()
        
        # 获取最新区块信息
        latest_block = None
        if info['chain_length'] > 0:
            latest_block = self.node.blockchain.get_latest_block()
            latest_block_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest_block.timestamp))
        else:
            latest_block_time = "N/A"
        
        self.blockchain_info_var.set(
            f"链长度: {info['chain_length']}\n"
            f"待处理交易: {info['pending_transactions']}\n"
            f"链是否有效: {info['is_valid']}\n"
            f"最新区块时间: {latest_block_time}"
        )
    
    def update_stake_info(self):
        """更新质押信息"""
        if not self.current_wallet or not self.node:
            return
        
        staked = self.current_wallet.get_staked_amount()
        
        # 检查是否是验证者
        validator_info = self.current_wallet.get_validator_info(self.node)
        
        if validator_info:
            self.stake_info_var.set(
                f"质押金额: {staked}\n"
                f"质押年龄: {validator_info['stake_age']:.2f} 天\n"
                f"权重: {validator_info['weight']:.2f}\n"
                f"状态: 验证者"
            )
        else:
            self.stake_info_var.set(
                f"质押金额: {staked}\n"
                f"状态: {'已质押' if staked > 0 else '未质押'}"
            )
    
    def show_blockchain_details(self):
        """显示区块链详情"""
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        # 创建对话框
        details_dialog = tk.Toplevel(self.root)
        details_dialog.title("区块链详情")
        details_dialog.geometry("700x500")
        
        # 创建选项卡
        notebook = ttk.Notebook(details_dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 区块选项卡
        blocks_frame = ttk.Frame(notebook)
        notebook.add(blocks_frame, text="区块")
        
        # 区块列表
        blocks_tree = ttk.Treeview(blocks_frame, columns=("index", "hash", "validator", "txs", "time"), show="headings")
        blocks_tree.heading("index", text="索引")
        blocks_tree.heading("hash", text="哈希")
        blocks_tree.heading("validator", text="验证者")
        blocks_tree.heading("txs", text="交易数")
        blocks_tree.heading("time", text="时间")
        blocks_tree.column("index", width=50)
        blocks_tree.column("hash", width=200)
        blocks_tree.column("validator", width=150)
        blocks_tree.column("txs", width=70)
        blocks_tree.column("time", width=150)
        blocks_tree.pack(fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        blocks_scrollbar = ttk.Scrollbar(blocks_frame, orient="vertical", command=blocks_tree.yview)
        blocks_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        blocks_tree.configure(yscrollcommand=blocks_scrollbar.set)
        
        # 填充区块数据
        for block in self.node.blockchain.chain:
            block_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block.timestamp))
            blocks_tree.insert("", tk.END, values=(
                block.index,
                block.hash[:20] + "...",
                block.validator,
                len(block.transactions),
                block_time
            ))
        
        # 待处理交易选项卡
        pending_frame = ttk.Frame(notebook)
        notebook.add(pending_frame, text="待处理交易")
        
        # 待处理交易列表
        pending_tree = ttk.Treeview(pending_frame, columns=("id", "sender", "recipient", "amount", "fee"), show="headings")
        pending_tree.heading("id", text="交易ID")
        pending_tree.heading("sender", text="发送方")
        pending_tree.heading("recipient", text="接收方")
        pending_tree.heading("amount", text="金额")
        pending_tree.heading("fee", text="费用")
        pending_tree.column("id", width=100)
        pending_tree.column("sender", width=150)
        pending_tree.column("recipient", width=150)
        pending_tree.column("amount", width=70)
        pending_tree.column("fee", width=70)
        pending_tree.pack(fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        pending_scrollbar = ttk.Scrollbar(pending_frame, orient="vertical", command=pending_tree.yview)
        pending_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        pending_tree.configure(yscrollcommand=pending_scrollbar.set)
        
        # 填充待处理交易数据
        for tx in self.node.blockchain.pending_transactions:
            pending_tree.insert("", tk.END, values=(
                tx.transaction_id[:10] + "...",
                tx.sender,
                tx.recipient,
                tx.amount,
                tx.fee
            ))
    
    def show_validator_info(self):
        """显示验证者信息"""
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        validators = self.node.get_validator_info()
        
        if not validators:
            messagebox.showinfo("提示", "没有验证者")
            return
        
        # 创建对话框
        validator_dialog = tk.Toplevel(self.root)
        validator_dialog.title("验证者信息")
        validator_dialog.geometry("600x400")
        
        # 验证者列表
        validator_tree = ttk.Treeview(validator_dialog, columns=("address", "stake", "age", "weight"), show="headings")
        validator_tree.heading("address", text="地址")
        validator_tree.heading("stake", text="质押金额")
        validator_tree.heading("age", text="质押年龄(天)")
        validator_tree.heading("weight", text="权重")
        validator_tree.column("address", width=200)
        validator_tree.column("stake", width=100)
        validator_tree.column("age", width=100)
        validator_tree.column("weight", width=100)
        validator_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        validator_scrollbar = ttk.Scrollbar(validator_dialog, orient="vertical", command=validator_tree.yview)
        validator_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        validator_tree.configure(yscrollcommand=validator_scrollbar.set)
        
        # 填充验证者数据
        for validator in validators:
            is_current = " (当前钱包)" if self.current_wallet and validator['address'] == self.current_wallet.address else ""
            validator_tree.insert("", tk.END, values=(
                validator['address'] + is_current,
                validator['stake_amount'],
                f"{validator['stake_age']:.2f}",
                f"{validator['weight']:.2f}"
            ))
    
    def show_bills(self):
        """显示账单"""
        if not self.current_wallet:
            messagebox.showerror("错误", "请先选择钱包")
            return
        
        bills = self.current_wallet.bill_manager.bills
        
        if not bills:
            messagebox.showinfo("提示", "没有账单")
            return
        
        # 创建对话框
        bill_dialog = tk.Toplevel(self.root)
        bill_dialog.title("账单列表")
        bill_dialog.geometry("700x400")
        
        # 账单列表
        bill_tree = ttk.Treeview(bill_dialog, columns=("id", "payer", "payee", "amount", "description"), show="headings")
        bill_tree.heading("id", text="账单ID")
        bill_tree.heading("payer", text="付款方")
        bill_tree.heading("payee", text="收款方")
        bill_tree.heading("amount", text="金额")
        bill_tree.heading("description", text="描述")
        bill_tree.column("id", width=100)
        bill_tree.column("payer", width=150)
        bill_tree.column("payee", width=150)
        bill_tree.column("amount", width=70)
        bill_tree.column("description", width=200)
        bill_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        bill_scrollbar = ttk.Scrollbar(bill_dialog, orient="vertical", command=bill_tree.yview)
        bill_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        bill_tree.configure(yscrollcommand=bill_scrollbar.set)
        
        # 填充账单数据
        for bill_id, bill in bills.items():
            bill_tree.insert("", tk.END, values=(
                bill_id[:10] + "...",
                bill.payer,
                bill.payee,
                bill.amount,
                bill.description
            ))
        
        # 添加支付按钮
        def on_pay_selected():
            selected = bill_tree.selection()
            if not selected:
                messagebox.showerror("错误", "请先选择账单")
                return
            
            bill_id = bill_tree.item(selected[0], "values")[0]
            bill_id = bill_id.replace("...", "")  # 移除省略号
            
            # 查找完整的账单ID
            full_bill_id = None
            for bid in bills.keys():
                if bid.startswith(bill_id):
                    full_bill_id = bid
                    break
            
            if full_bill_id:
                self.pay_bill(full_bill_id)
                bill_dialog.destroy()  # 关闭对话框
            else:
                messagebox.showerror("错误", f"找不到账单 {bill_id}")
        
        ttk.Button(bill_dialog, text="支付选中账单", command=on_pay_selected).pack(pady=10)
    
    def update_transaction_history(self):
        """更新交易历史"""
        if not self.current_wallet or not self.node:
            return
        
        # 清空列表
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # 获取交易历史
        history = []
        
        # 从区块链中获取与当前钱包相关的交易
        for block in self.node.blockchain.chain:
            for tx in block.transactions:
                if tx.sender == self.current_wallet.address or tx.recipient == self.current_wallet.address:
                    history.append(tx.to_dict())
        
        # 从待处理交易中获取与当前钱包相关的交易
        for tx in self.node.blockchain.pending_transactions:
            if tx.sender == self.current_wallet.address or tx.recipient == self.current_wallet.address:
                tx_dict = tx.to_dict()
                tx_dict['pending'] = True
                history.append(tx_dict)
        
        # 按时间戳排序
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # 添加交易记录
        for tx in history:
            tx_type = "发送" if tx['sender'] == self.current_wallet.address else "接收"
            if tx.get('pending'):
                tx_type += "(待处理)"
                
            amount = tx['amount']
            if tx_type.startswith("发送"):
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
    
    def pay_bill(self, bill_id=None):
        """
        支付账单
        
        Args:
            bill_id: 账单ID，如果为None则弹出对话框询问
        """
        if not self.current_wallet:
            messagebox.showerror("错误", "请先选择钱包")
            return
        
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        if not bill_id:
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
        if not self.current_wallet:
            messagebox.showerror("错误", "请先选择钱包")
            return
        
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        amount = simpledialog.askfloat("质押代币", "请输入质押金额:")
        if not amount or amount <= 0:
            messagebox.showerror("错误", "质押金额必须大于0")
            return
        
        # 质押代币
        if self.current_wallet.stake_tokens(amount, self.node):
            messagebox.showinfo("成功", f"已质押 {amount} 代币")
            self.status_var.set(f"已质押 {amount} 代币")
            
            # 更新质押信息
            self.update_stake_info()
            self.update_balance()
            
            # 广播验证者信息
            if self.node.node_id in self.node.pos_consensus.validators:
                self.node.p2p_node.broadcast_validator_info(
                    self.current_wallet.staked_amount,
                    self.node.pos_consensus
                )
        else:
            messagebox.showerror("错误", f"质押代币失败")
    
    def unstake_tokens(self):
        """取消质押"""
        if not self.current_wallet:
            messagebox.showerror("错误", "请先选择钱包")
            return
        
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        staked_amount = self.current_wallet.get_staked_amount()
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
        if self.current_wallet.unstake_tokens(amount, self.node):
            messagebox.showinfo("成功", f"已取消质押 {amount} 代币")
            self.status_var.set(f"已取消质押 {amount} 代币")
            
            # 更新质押信息
            self.update_stake_info()
            self.update_balance()
        else:
            messagebox.showerror("错误", f"取消质押失败")
    
    def auto_update(self):
        """自动更新UI信息"""
        while self.running:
            if self.node:
                self.update_blockchain_info()
            
            if self.current_wallet and self.node:
                self.update_balance()
                self.update_transaction_history()
                self.update_stake_info()
            
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