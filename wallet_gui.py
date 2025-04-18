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
        
        # 设置初始窗口大小，但允许调整
        self.root.geometry("1280x1024")
        self.root.minsize(800, 600)  # 设置最小窗口大小
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
        
        # 绑定窗口大小变化事件
        self.root.bind("<Configure>", self.on_window_resize)
    
    def on_window_resize(self, event):
        """处理窗口大小变化事件"""
        # 只处理根窗口的大小变化
        if event.widget == self.root:
            # 调整主框架的大小
            self.main_frame.configure(width=event.width-20, height=event.height-40)
            
            # 调整左右框架的宽度比例
            self.main_frame.update()
            frame_width = self.main_frame.winfo_width()
            self.left_frame.configure(width=frame_width * 0.45)
            self.right_frame.configure(width=frame_width * 0.45)
    
    def create_widgets(self):
        """创建UI组件"""
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建左侧面板（带滚动条）
        left_container = ttk.Frame(self.main_frame)
        left_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 添加滚动条
        left_scrollbar = ttk.Scrollbar(left_container)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建画布用于滚动
        left_canvas = tk.Canvas(left_container)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 配置滚动条与画布
        left_scrollbar.config(command=left_canvas.yview)
        left_canvas.config(yscrollcommand=left_scrollbar.set)
        
        # 在画布中创建框架
        self.left_frame = ttk.LabelFrame(left_canvas, text="钱包和节点", padding=10)
        left_canvas_window = left_canvas.create_window((0, 0), window=self.left_frame, anchor="nw")

        # 添加配置更新函数，确保框架宽度正确
        def configure_left_frame(event):
            # 设置框架宽度为画布宽度
            canvas_width = left_canvas.winfo_width()
            left_canvas.itemconfig(left_canvas_window, width=canvas_width)

        left_canvas.bind('<Configure>', configure_left_frame)
        self.left_frame.bind("<Configure>", lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
        
        self.right_frame = ttk.LabelFrame(self.main_frame, text="交易和账单", padding=10)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧面板内容
        # 钱包列表
        wallet_frame = ttk.LabelFrame(self.left_frame, text="钱包列表", padding=10)
        wallet_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 钱包列表视图
        wallet_tree_frame = ttk.Frame(wallet_frame)
        wallet_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.wallet_tree = ttk.Treeview(wallet_tree_frame, columns=("name", "address"), show="headings")
        self.wallet_tree.heading("name", text="名称")
        self.wallet_tree.heading("address", text="地址")
        self.wallet_tree.column("name", width=100, minwidth=80)
        self.wallet_tree.column("address", width=200, minwidth=150)
        self.wallet_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.wallet_tree.bind("<Double-1>", self.on_wallet_select)
        
        # 添加滚动条
        wallet_scrollbar = ttk.Scrollbar(wallet_tree_frame, orient="vertical", command=self.wallet_tree.yview)
        wallet_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.wallet_tree.configure(yscrollcommand=wallet_scrollbar.set)
        
        # 钱包操作按钮
        wallet_btn_frame = ttk.Frame(wallet_frame)
        wallet_btn_frame.pack(fill=tk.X, pady=5)
        
        # 使用网格布局来排列按钮，确保在窗口缩小时仍然可见
        ttk.Button(wallet_btn_frame, text="创建钱包", command=self.create_wallet).grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        ttk.Button(wallet_btn_frame, text="刷新列表", command=self.update_wallet_list).grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Button(wallet_btn_frame, text="导出钱包", command=self.export_wallet).grid(row=1, column=0, padx=5, pady=2, sticky="ew")
        ttk.Button(wallet_btn_frame, text="导入钱包", command=self.import_wallet).grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        
        # 配置网格列权重，使按钮能够均匀分布
        wallet_btn_frame.columnconfigure(0, weight=1)
        wallet_btn_frame.columnconfigure(1, weight=1)
        
        # 节点控制
        node_frame = ttk.LabelFrame(self.left_frame, text="节点控制", padding=10)
        node_frame.pack(fill=tk.BOTH, pady=5)
        
        # 节点状态
        self.node_status_var = tk.StringVar(value="节点未启动")
        ttk.Label(node_frame, textvariable=self.node_status_var, wraplength=350).pack(fill=tk.X, pady=5)
        
        # 节点操作按钮
        node_btn_frame = ttk.Frame(node_frame)
        node_btn_frame.pack(fill=tk.X, pady=5)
        
        # 使用网格布局
        ttk.Button(node_btn_frame, text="启动节点", command=self.start_node).grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        ttk.Button(node_btn_frame, text="连接网络", command=self.connect_to_network).grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Button(node_btn_frame, text="查看网络", command=self.show_network_info).grid(row=0, column=2, padx=5, pady=2, sticky="ew")
        
        # 配置网格列权重
        node_btn_frame.columnconfigure(0, weight=1)
        node_btn_frame.columnconfigure(1, weight=1)
        node_btn_frame.columnconfigure(2, weight=1)
        
        # 区块链信息
        blockchain_frame = ttk.LabelFrame(self.left_frame, text="区块链信息", padding=10)
        blockchain_frame.pack(fill=tk.BOTH, pady=5)
        
        # 区块链状态
        self.blockchain_info_var = tk.StringVar(value="未连接到区块链")
        ttk.Label(blockchain_frame, textvariable=self.blockchain_info_var, wraplength=350).pack(fill=tk.X, pady=5)
        
        # 区块链操作按钮
        blockchain_btn_frame = ttk.Frame(blockchain_frame)
        blockchain_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(blockchain_btn_frame, text="查看详情", command=self.show_blockchain_details).pack(fill=tk.X, padx=5)
        
        # 质押控制
        stake_frame = ttk.LabelFrame(self.left_frame, text="质押控制", padding=10)
        stake_frame.pack(fill=tk.BOTH, pady=5)
        
        # 质押状态
        self.stake_info_var = tk.StringVar(value="未质押")
        ttk.Label(stake_frame, textvariable=self.stake_info_var, wraplength=350).pack(fill=tk.X, pady=5)
        
        # 质押操作按钮
        stake_btn_frame = ttk.Frame(stake_frame)
        stake_btn_frame.pack(fill=tk.X, pady=5)
        
        # 使用网格布局
        ttk.Button(stake_btn_frame, text="质押代币", command=self.stake_tokens).grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        ttk.Button(stake_btn_frame, text="取消质押", command=self.unstake_tokens).grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Button(stake_btn_frame, text="验证者信息", command=self.show_validator_info).grid(row=0, column=2, padx=5, pady=2, sticky="ew")
        
        # 配置网格列权重
        stake_btn_frame.columnconfigure(0, weight=1)
        stake_btn_frame.columnconfigure(1, weight=1)
        stake_btn_frame.columnconfigure(2, weight=1)
        
        # 右侧面板内容
        # 当前钱包信息
        wallet_info_frame = ttk.LabelFrame(self.right_frame, text="当前钱包", padding=10)
        wallet_info_frame.pack(fill=tk.X, pady=5)
        
        self.current_wallet_var = tk.StringVar(value="未选择钱包")
        ttk.Label(wallet_info_frame, textvariable=self.current_wallet_var, wraplength=350).pack(fill=tk.X, pady=5)
        
        self.balance_var = tk.StringVar(value="余额: 0.0")
        ttk.Label(wallet_info_frame, textvariable=self.balance_var, wraplength=350).pack(fill=tk.X, pady=5)
        
        # 交易操作
        transaction_frame = ttk.LabelFrame(self.right_frame, text="创建交易", padding=10)
        transaction_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(transaction_frame, text="接收方地址:").pack(anchor=tk.W, pady=2)
        self.recipient_entry = ttk.Entry(transaction_frame)
        self.recipient_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(transaction_frame, text="金额:").pack(anchor=tk.W, pady=2)
        self.amount_entry = ttk.Entry(transaction_frame)
        self.amount_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(transaction_frame, text="费用:").pack(anchor=tk.W, pady=2)
        self.fee_entry = ttk.Entry(transaction_frame)
        self.fee_entry.insert(0, "0.001")
        self.fee_entry.pack(fill=tk.X, pady=2)
        
        ttk.Button(transaction_frame, text="创建交易", command=self.create_transaction).pack(fill=tk.X, pady=5)
        
        # 账单操作
        bill_frame = ttk.LabelFrame(self.right_frame, text="账单操作", padding=10)
        bill_frame.pack(fill=tk.X, pady=5)
        
        bill_btn_frame = ttk.Frame(bill_frame)
        bill_btn_frame.pack(fill=tk.X, pady=5)
        
        # 使用网格布局
        ttk.Button(bill_btn_frame, text="创建账单", command=self.create_bill).grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        ttk.Button(bill_btn_frame, text="支付账单", command=self.pay_bill).grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Button(bill_btn_frame, text="查看账单", command=self.show_bills).grid(row=0, column=2, padx=5, pady=2, sticky="ew")
        
        # 配置网格列权重
        bill_btn_frame.columnconfigure(0, weight=1)
        bill_btn_frame.columnconfigure(1, weight=1)
        bill_btn_frame.columnconfigure(2, weight=1)
        
        # 交易历史
        history_frame = ttk.LabelFrame(self.right_frame, text="交易历史", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建包含树形视图和滚动条的框架
        history_tree_frame = ttk.Frame(history_frame)
        history_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # 交易历史列表
        self.history_tree = ttk.Treeview(history_tree_frame, columns=("id", "type", "amount", "time"), show="headings")
        self.history_tree.heading("id", text="交易ID")
        self.history_tree.heading("type", text="类型")
        self.history_tree.heading("amount", text="金额")
        self.history_tree.heading("time", text="时间")
        self.history_tree.column("id", width=100, minwidth=80)
        self.history_tree.column("type", width=80, minwidth=60)
        self.history_tree.column("amount", width=80, minwidth=60)
        self.history_tree.column("time", width=150, minwidth=120)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加垂直滚动条
        history_scrollbar_y = ttk.Scrollbar(history_tree_frame, orient="vertical", command=self.history_tree.yview)
        history_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.configure(yscrollcommand=history_scrollbar_y.set)
        
        # 添加水平滚动条
        history_scrollbar_x = ttk.Scrollbar(history_frame, orient="horizontal", command=self.history_tree.xview)
        history_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.history_tree.configure(xscrollcommand=history_scrollbar_x.set)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        

        tendermint_frame = ttk.LabelFrame(node_frame, text="Tendermint共识", padding=5)
        tendermint_frame.pack(fill=tk.X, pady=5)

        self.tendermint_status_var = tk.StringVar(value="未启用")
        ttk.Label(tendermint_frame, textvariable=self.tendermint_status_var).pack(side=tk.LEFT, padx=5)

        self.tendermint_btn = ttk.Button(tendermint_frame, text="启用Tendermint", command=self.toggle_tendermint)
        self.tendermint_btn.pack(side=tk.RIGHT, padx=5)

                
    
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
        
        # 创建自定义对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("启动节点")
        dialog.geometry("300x250")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.attributes('-topmost', True)
        
        # 添加输入框
        ttk.Label(dialog, text="请输入主机地址:").pack(pady=5)
        host_entry = ttk.Entry(dialog)
        host_entry.pack(pady=5, fill=tk.X, padx=10)
        host_entry.insert(0, "127.0.0.1")
        
        ttk.Label(dialog, text="请输入端口号:").pack(pady=5)
        port_entry = ttk.Entry(dialog)
        port_entry.pack(pady=5, fill=tk.X, padx=10)
        port_entry.insert(0, "5005")
        
        # 确认按钮
        def on_confirm():
            host = host_entry.get().strip()
            try:
                port = int(port_entry.get().strip())
                dialog.destroy()
                
                # 启动节点的代码
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
                
                
            except ValueError:
                messagebox.showerror("错误", "端口必须是数字")
        
        ttk.Button(dialog, text="确认", command=on_confirm).pack(pady=10, fill=tk.X, padx=10)

    
    def connect_to_network(self):
        """连接到网络"""
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        # 创建连接对话框
        connect_dialog = tk.Toplevel(self.root)
        connect_dialog.title("连接到网络")
        connect_dialog.geometry("800x600")
        connect_dialog.transient(self.root)
        connect_dialog.grab_set()
        connect_dialog.transient(self.root)  # 设置为父窗口的临时窗口
        connect_dialog.grab_set()  # 获取焦点
        connect_dialog.attributes('-topmost', True)  # 设置为最顶层窗口

        # 手动连接框架
        manual_frame = ttk.LabelFrame(connect_dialog, text="手动连接", padding=10)
        manual_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(manual_frame, text="种子节点地址:").pack(anchor=tk.W)
        host_entry = ttk.Entry(manual_frame)
        host_entry.pack(fill=tk.X, pady=2)
        host_entry.insert(0, "127.0.0.1")
        
        ttk.Label(manual_frame, text="种子节点端口:").pack(anchor=tk.W)
        port_entry = ttk.Entry(manual_frame)
        port_entry.pack(fill=tk.X, pady=2)
        port_entry.insert(0, "5005")
        
        # 自动发现框架
        auto_frame = ttk.LabelFrame(connect_dialog, text="自动发现", padding=10)
        auto_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 预配置节点列表
        predefined_nodes = [
            ("主网节点1", "node1.example.com", 5005),
            ("主网节点2", "node2.example.com", 5005),
            ("测试网节点", "testnet.example.com", 5005),
            ("本地节点", "127.0.0.1", 5005)
        ]
        
        node_var = tk.StringVar()
        for i, (name, host, port) in enumerate(predefined_nodes):
            ttk.Radiobutton(
                auto_frame, 
                text=f"{name} ({host}:{port})", 
                value=f"{host}:{port}", 
                variable=node_var
            ).pack(anchor=tk.W, pady=2)
        
        # 如果有预定义节点，默认选择第一个
        if predefined_nodes:
            node_var.set(f"{predefined_nodes[0][1]}:{predefined_nodes[0][2]}")
        
        # 按钮框架
        btn_frame = ttk.Frame(connect_dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def on_manual_connect():
            host = host_entry.get().strip()
            try:
                port = int(port_entry.get().strip())
                if self.node.connect_to_network(host, port):
                    messagebox.showinfo("成功", f"已连接到网络节点 {host}:{port}")
                    self.status_var.set(f"已连接到网络节点 {host}:{port}")
                    
                    # 连接成功后自动发现其他节点
                    self.node.auto_discover_nodes()
                    
                    # 同步区块链
                    self.node.p2p_node.synchronize_blockchain()
                    
                    # 更新区块链信息
                    self.update_blockchain_info()
                    connect_dialog.destroy()
                else:
                    messagebox.showerror("错误", f"连接到网络节点 {host}:{port} 失败")
            except ValueError:
                messagebox.showerror("错误", "端口必须是数字")
        
        def on_auto_connect():
            if not node_var.get():
                messagebox.showerror("错误", "请选择一个预定义节点")
                return
            
            host, port = node_var.get().split(":")
            port = int(port)
            
            if self.node.connect_to_network(host, port):
                messagebox.showinfo("成功", f"已连接到网络节点 {host}:{port}")
                self.status_var.set(f"已连接到网络节点 {host}:{port}")
                
                # 连接成功后自动发现其他节点
                self.node.auto_discover_nodes()
                
                # 同步区块链
                self.node.p2p_node.synchronize_blockchain()
                
                # 更新区块链信息
                self.update_blockchain_info()
                connect_dialog.destroy()
            else:
                messagebox.showerror("错误", f"连接到网络节点 {host}:{port} 失败")
        
        ttk.Button(btn_frame, text="手动连接", command=on_manual_connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="自动连接", command=on_auto_connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=connect_dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
    # 修改 show_network_info 方法
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
        network_dialog.transient(self.root)  # 设置为父窗口的临时窗口
        network_dialog.grab_set()  # 获取焦点
        network_dialog.attributes('-topmost', True)  # 设置为最顶层窗口
        
        # 添加文本框
        text_frame = ttk.Frame(network_dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text = tk.Text(text_frame, wrap=tk.WORD)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(text_frame, command=text.yview)
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
        details_dialog.minsize(600, 400)
        
        # 创建选项卡
        notebook = ttk.Notebook(details_dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 区块选项卡
        blocks_frame = ttk.Frame(notebook)
        notebook.add(blocks_frame, text="区块")
        
        # 创建包含树形视图和滚动条的框架
        blocks_tree_frame = ttk.Frame(blocks_frame)
        blocks_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # 区块列表
        blocks_tree = ttk.Treeview(blocks_tree_frame, columns=("index", "hash", "validator", "txs", "time"), show="headings")
        blocks_tree.heading("index", text="索引")
        blocks_tree.heading("hash", text="哈希")
        blocks_tree.heading("validator", text="验证者")
        blocks_tree.heading("txs", text="交易数")
        blocks_tree.heading("time", text="时间")
        blocks_tree.column("index", width=50, minwidth=40)
        blocks_tree.column("hash", width=200, minwidth=150)
        blocks_tree.column("validator", width=150, minwidth=120)
        blocks_tree.column("txs", width=70, minwidth=50)
        blocks_tree.column("time", width=150, minwidth=120)
        blocks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加垂直滚动条
        blocks_scrollbar_y = ttk.Scrollbar(blocks_tree_frame, orient="vertical", command=blocks_tree.yview)
        blocks_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        blocks_tree.configure(yscrollcommand=blocks_scrollbar_y.set)
        
        # 添加水平滚动条
        blocks_scrollbar_x = ttk.Scrollbar(blocks_frame, orient="horizontal", command=blocks_tree.xview)
        blocks_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        blocks_tree.configure(xscrollcommand=blocks_scrollbar_x.set)
        
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
        
        # 创建包含树形视图和滚动条的框架
        pending_tree_frame = ttk.Frame(pending_frame)
        pending_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # 待处理交易列表
        pending_tree = ttk.Treeview(pending_tree_frame, columns=("id", "sender", "recipient", "amount", "fee"), show="headings")
        pending_tree.heading("id", text="交易ID")
        pending_tree.heading("sender", text="发送方")
        pending_tree.heading("recipient", text="接收方")
        pending_tree.heading("amount", text="金额")
        pending_tree.heading("fee", text="费用")
        pending_tree.column("id", width=100, minwidth=80)
        pending_tree.column("sender", width=150, minwidth=120)
        pending_tree.column("recipient", width=150, minwidth=120)
        pending_tree.column("amount", width=70, minwidth=50)
        pending_tree.column("fee", width=70, minwidth=50)
        pending_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加垂直滚动条
        pending_scrollbar_y = ttk.Scrollbar(pending_tree_frame, orient="vertical", command=pending_tree.yview)
        pending_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        pending_tree.configure(yscrollcommand=pending_scrollbar_y.set)
        
        # 添加水平滚动条
        pending_scrollbar_x = ttk.Scrollbar(pending_frame, orient="horizontal", command=pending_tree.xview)
        pending_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        pending_tree.configure(xscrollcommand=pending_scrollbar_x.set)
        
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
        validator_dialog.geometry("700x500")
        validator_dialog.minsize(600, 400)
        
        # 创建选项卡
        notebook = ttk.Notebook(validator_dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 验证者列表选项卡
        validators_frame = ttk.Frame(notebook)
        notebook.add(validators_frame, text="验证者列表")
        
        # 创建包含树形视图和滚动条的框架
        validator_tree_frame = ttk.Frame(validators_frame)
        validator_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 验证者列表
        validator_tree = ttk.Treeview(validator_tree_frame, columns=("address", "stake", "age", "weight", "blocks"), show="headings")
        validator_tree.heading("address", text="地址")
        validator_tree.heading("stake", text="质押金额")
        validator_tree.heading("age", text="质押年龄(天)")
        validator_tree.heading("weight", text="权重")
        validator_tree.heading("blocks", text="生成区块数")
        validator_tree.column("address", width=200, minwidth=150)
        validator_tree.column("stake", width=100, minwidth=80)
        validator_tree.column("age", width=100, minwidth=80)
        validator_tree.column("weight", width=100, minwidth=80)
        validator_tree.column("blocks", width=100, minwidth=80)
        validator_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加垂直滚动条
        validator_scrollbar_y = ttk.Scrollbar(validator_tree_frame, orient="vertical", command=validator_tree.yview)
        validator_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        validator_tree.configure(yscrollcommand=validator_scrollbar_y.set)
        
        # 添加水平滚动条
        validator_scrollbar_x = ttk.Scrollbar(validators_frame, orient="horizontal", command=validator_tree.xview)
        validator_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        validator_tree.configure(xscrollcommand=validator_scrollbar_x.set)
        
        # 统计每个验证者生成的区块数
        validator_blocks = {}
        for validator in validators:
            validator_blocks[validator['address']] = 0
        
        for block in self.node.blockchain.chain:
            if block.validator in validator_blocks:
                validator_blocks[block.validator] += 1
        
        # 填充验证者数据
        for validator in validators:
            is_current = " (当前钱包)" if self.current_wallet and validator['address'] == self.current_wallet.address else ""
            blocks_count = validator_blocks.get(validator['address'], 0)
            validator_tree.insert("", tk.END, values=(
                validator['address'] + is_current,
                validator['stake_amount'],
                f"{validator['stake_age']:.2f}",
                f"{validator['weight']:.2f}",
                blocks_count
            ))
        
        # 当前验证者状态选项卡（如果当前钱包是验证者）
        if self.current_wallet:
            current_validator = None
            for validator in validators:
                if validator['address'] == self.current_wallet.address:
                    current_validator = validator
                    break
            
            if current_validator:
                current_frame = ttk.Frame(notebook)
                notebook.add(current_frame, text="当前验证者状态")
                
                # 创建详细信息显示
                info_frame = ttk.LabelFrame(current_frame, text="验证者详细信息", padding=10)
                info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                # 获取更多详细信息
                blocks_validated = validator_blocks.get(self.current_wallet.address, 0)
                next_forge_time = time.time() + (self.node.pos_consensus.block_time - 
                                            (time.time() - self.node.pos_consensus.last_block_time))
                
                # 计算预计收益
                expected_reward = 0
                if blocks_validated > 0:
                    # 计算平均每个区块的奖励
                    total_reward = 0
                    reward_blocks = 0
                    for block in self.node.blockchain.chain:
                        if block.validator == self.current_wallet.address:
                            for tx in block.transactions:
                                if tx.sender == "COINBASE" and tx.recipient == self.current_wallet.address:
                                    total_reward += tx.amount
                                    reward_blocks += 1
                    
                    if reward_blocks > 0:
                        avg_reward = total_reward / reward_blocks
                        # 预计每天的区块数
                        blocks_per_day = 24 * 60 * 60 / self.node.pos_consensus.block_time
                        # 根据权重比例计算预期每天生成的区块数
                        total_weight = sum(v['weight'] for v in validators)
                        weight_ratio = current_validator['weight'] / total_weight if total_weight > 0 else 0
                        expected_blocks = blocks_per_day * weight_ratio
                        expected_reward = expected_blocks * avg_reward
                
                # 显示详细信息
                info_text = f"""
    地址: {self.current_wallet.address}
    质押金额: {current_validator['stake_amount']}
    质押年龄: {current_validator['stake_age']:.2f} 天
    权重: {current_validator['weight']:.2f}
    生成区块数: {blocks_validated}
    下次可能生成区块时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(next_forge_time))}
    预计每日收益: {expected_reward:.6f}
                """
                
                # 使用滚动文本框显示信息
                info_text_frame = ttk.Frame(info_frame)
                info_text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                info_text_widget = tk.Text(info_text_frame, wrap=tk.WORD, height=10)
                info_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                info_text_widget.insert(tk.END, info_text)
                info_text_widget.config(state=tk.DISABLED)
                
                info_scrollbar = ttk.Scrollbar(info_text_frame, command=info_text_widget.yview)
                info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                info_text_widget.config(yscrollcommand=info_scrollbar.set)
                
                # 添加区块生成历史
                history_frame = ttk.LabelFrame(current_frame, text="区块生成历史", padding=10)
                history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                # 创建包含树形视图和滚动条的框架
                history_tree_frame = ttk.Frame(history_frame)
                history_tree_frame.pack(fill=tk.BOTH, expand=True)
                
                history_tree = ttk.Treeview(history_tree_frame, columns=("index", "time", "txs", "reward"), show="headings")
                history_tree.heading("index", text="区块索引")
                history_tree.heading("time", text="生成时间")
                history_tree.heading("txs", text="交易数")
                history_tree.heading("reward", text="奖励")
                history_tree.column("index", width=80, minwidth=60)
                history_tree.column("time", width=150, minwidth=120)
                history_tree.column("txs", width=80, minwidth=60)
                history_tree.column("reward", width=100, minwidth=80)
                history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                
                # 添加垂直滚动条
                history_scrollbar_y = ttk.Scrollbar(history_tree_frame, orient="vertical", command=history_tree.yview)
                history_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
                history_tree.configure(yscrollcommand=history_scrollbar_y.set)
                
                # 添加水平滚动条
                history_scrollbar_x = ttk.Scrollbar(history_frame, orient="horizontal", command=history_tree.xview)
                history_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
                history_tree.configure(xscrollcommand=history_scrollbar_x.set)
                
                # 填充区块生成历史
                for block in reversed(self.node.blockchain.chain):
                    if block.validator == self.current_wallet.address:
                        # 查找奖励交易
                        reward = 0
                        for tx in block.transactions:
                            if tx.sender == "COINBASE" and tx.recipient == self.current_wallet.address:
                                reward = tx.amount
                                break
                        
                        block_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block.timestamp))
                        history_tree.insert("", tk.END, values=(
                            block.index,
                            block_time,
                            len(block.transactions),
                            f"{reward:.6f}"
                        ))
        
        # 网络验证状态选项卡
        network_frame = ttk.Frame(notebook)
        notebook.add(network_frame, text="网络验证状态")
        
        # 创建网络验证状态信息
        network_info_frame = ttk.Frame(network_frame, padding=10)
        network_info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 获取网络验证状态信息
        total_stake = sum(validator['stake_amount'] for validator in validators)
        active_validators = len(validators)
        avg_stake = total_stake / active_validators if active_validators > 0 else 0
        
        # 计算区块生成统计
        block_count = len(self.node.blockchain.chain)
        if block_count > 1:  # 跳过创世区块
            avg_block_time = 0
            if block_count > 2:
                total_time = self.node.blockchain.chain[-1].timestamp - self.node.blockchain.chain[1].timestamp
                avg_block_time = total_time / (block_count - 2)
            
            last_block_time = time.strftime('%Y-%m-%d %H:%M:%S', 
                                        time.localtime(self.node.blockchain.chain[-1].timestamp))
            
            network_info = f"""
    网络验证状态:
    活跃验证者数量: {active_validators}
    总质押金额: {total_stake}
    平均质押金额: {avg_stake:.2f}
    区块链长度: {block_count}
    平均区块生成时间: {avg_block_time:.2f} 秒
    最新区块生成时间: {last_block_time}
    目标区块时间: {self.node.pos_consensus.block_time} 秒
            """
            
            # 使用滚动文本框显示信息
            network_text_frame = ttk.Frame(network_info_frame)
            network_text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            network_text_widget = tk.Text(network_text_frame, wrap=tk.WORD, height=10)
            network_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            network_text_widget.insert(tk.END, network_info)
            network_text_widget.config(state=tk.DISABLED)
            
            network_scrollbar = ttk.Scrollbar(network_text_frame, command=network_text_widget.yview)
            network_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            network_text_widget.config(yscrollcommand=network_scrollbar.set)
            
            # 添加验证者分布图
            # 表
            chart_frame = ttk.LabelFrame(network_frame, text="验证者权重分布", padding=10)
            chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 创建滚动文本框显示图表
            chart_text_frame = ttk.Frame(chart_frame)
            chart_text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            chart_text_widget = tk.Text(chart_text_frame, wrap=tk.WORD, font=("Courier", 10))
            chart_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # 按权重排序
            sorted_validators = sorted(validators, key=lambda v: v['weight'], reverse=True)
            
            chart_text = "验证者权重分布:\n\n"
            for validator in sorted_validators:
                weight_percent = (validator['weight'] / sum(v['weight'] for v in validators)) * 100 if validators else 0
                bars = int(weight_percent / 2)  # 每2%一个字符
                chart_text += f"{validator['address'][:10]}...: {validator['weight']:.2f} ({weight_percent:.2f}%) "
                chart_text += "█" * bars + "\n"
            
            chart_text_widget.insert(tk.END, chart_text)
            chart_text_widget.config(state=tk.DISABLED)
            
            chart_scrollbar = ttk.Scrollbar(chart_text_frame, command=chart_text_widget.yview)
            chart_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            chart_text_widget.config(yscrollcommand=chart_scrollbar.set)
    
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
        bill_dialog.minsize(600, 300)
        
        # 创建包含树形视图和滚动条的框架
        bill_tree_frame = ttk.Frame(bill_dialog)
        bill_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 账单列表
        bill_tree = ttk.Treeview(bill_tree_frame, columns=("id", "payer", "payee", "amount", "description"), show="headings")
        bill_tree.heading("id", text="账单ID")
        bill_tree.heading("payer", text="付款方")
        bill_tree.heading("payee", text="收款方")
        bill_tree.heading("amount", text="金额")
        bill_tree.heading("description", text="描述")
        bill_tree.column("id", width=100, minwidth=80)
        bill_tree.column("payer", width=150, minwidth=120)
        bill_tree.column("payee", width=150, minwidth=120)
        bill_tree.column("amount", width=70, minwidth=50)
        bill_tree.column("description", width=200, minwidth=150)
        bill_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加垂直滚动条
        bill_scrollbar_y = ttk.Scrollbar(bill_tree_frame, orient="vertical", command=bill_tree.yview)
        bill_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        bill_tree.configure(yscrollcommand=bill_scrollbar_y.set)
        
        # 添加水平滚动条
        bill_scrollbar_x = ttk.Scrollbar(bill_dialog, orient="horizontal", command=bill_tree.xview)
        bill_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X, padx=10)
        bill_tree.configure(xscrollcommand=bill_scrollbar_x.set)
        
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
    
    # 在 wallet_gui.py 中的 WalletGUI 类中修改

    def update_transaction_history(self):
        """更新交易历史"""
        if not self.current_wallet or not self.node:
            return
        
        # 清空列表
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # 获取交易历史
        history = self.current_wallet.get_transaction_history(self.node)
        
        # 如果没有从存储中获取到历史，则从区块链中获取
        if not history:
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
        
        # 创建质押对话框
        stake_dialog = tk.Toplevel(self.root)
        stake_dialog.title("质押代币")
        stake_dialog.geometry("800x600")
        stake_dialog.minsize(600, 400)
        stake_dialog.transient(self.root)
        stake_dialog.grab_set()
        
        # 获取当前余额和质押信息
        balance = self.current_wallet.get_balance(self.node)
        staked = self.current_wallet.get_staked_amount()
        
        # 显示当前信息
        info_frame = ttk.LabelFrame(stake_dialog, text="当前信息", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        info_text = f"""
    可用余额: {balance}
    已质押金额: {staked}
    总资产: {balance + staked}
    最低质押要求: {self.node.pos_consensus.min_stake_amount}
        """
        
        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT, wraplength=700)
        info_label.pack(padx=10, pady=10)
        
        # 质押金额输入
        stake_frame = ttk.LabelFrame(stake_dialog, text="质押设置", padding=10)
        stake_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(stake_frame, text="质押金额:").pack(anchor=tk.W)
        amount_var = tk.StringVar()
        amount_entry = ttk.Entry(stake_frame, textvariable=amount_var)
        amount_entry.pack(fill=tk.X, pady=2)
        
        # 添加快速选择按钮
        quick_frame = ttk.Frame(stake_frame)
        quick_frame.pack(fill=tk.X, pady=5)
        
        def set_amount(percent):
            amount = balance * percent / 100
            amount_var.set(f"{amount:.2f}")
        
        # 使用网格布局
        ttk.Button(quick_frame, text="25%", command=lambda: set_amount(25)).grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        ttk.Button(quick_frame, text="50%", command=lambda: set_amount(50)).grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Button(quick_frame, text="75%", command=lambda: set_amount(75)).grid(row=0, column=2, padx=5, pady=2, sticky="ew")
        ttk.Button(quick_frame, text="最大", command=lambda: set_amount(100)).grid(row=0, column=3, padx=5, pady=2, sticky="ew")
        
        # 配置网格列权重
        for i in range(4):
            quick_frame.columnconfigure(i, weight=1)
        
        # 预计收益信息
        reward_frame = ttk.LabelFrame(stake_dialog, text="预计收益", padding=10)
        reward_frame.pack(fill=tk.X, padx=10, pady=10)
        
        reward_var = tk.StringVar(value="输入质押金额以查看预计收益")
        reward_label = ttk.Label(reward_frame, textvariable=reward_var, justify=tk.LEFT, wraplength=700)
        reward_label.pack(padx=10, pady=10)
        
        # 计算预计收益
        def calculate_reward(*args):
            try:
                amount = float(amount_var.get())
                # if amount <= 0:
                #     reward_var.set("质押金额必须大于0")
                #     return
                
                # 获取验证者信息
                validators = self.node.get_validator_info()
                total_stake = sum(v['stake_amount'] for v in validators)
                
                # 计算新的总质押和权重比例
                new_total_stake = total_stake + amount
                weight_ratio = amount / new_total_stake if new_total_stake > 0 else 0
                
                # 计算预计每天的区块数和奖励
                blocks_per_day = 24 * 60 * 60 / self.node.pos_consensus.block_time
                expected_blocks = blocks_per_day * weight_ratio
                
                # 估算每个区块的奖励
                base_reward = self.node.reward_calculator.calculate_block_reward(len(self.node.blockchain.chain))
                
                expected_daily_reward = expected_blocks * base_reward
                expected_monthly_reward = expected_daily_reward * 30
                expected_yearly_reward = expected_daily_reward * 365
                
                # 计算年化收益率
                apy = (expected_yearly_reward / amount) * 100 if amount > 0 else 0
                
                reward_text = f"""
    预计每日收益: {expected_daily_reward:.6f}
    预计每月收益: {expected_monthly_reward:.6f}
    预计每年收益: {expected_yearly_reward:.6f}
    预计年化收益率: {apy:.2f}%
                """
                
                reward_var.set(reward_text)
            except ValueError:
                reward_var.set("请输入有效的质押金额")
        
        # 监听金额变化
        amount_var.trace_add("write", calculate_reward)
        
        # 按钮操作
        btn_frame = ttk.Frame(stake_dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def on_stake():
            try:
                amount = float(amount_var.get())
                # if amount <= 0:
                #     messagebox.showerror("错误", "质押金额必须大于0")
                #     return
                
                if amount > balance:
                    messagebox.showerror("错误", f"余额不足: {balance} < {amount}")
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
                    
                    stake_dialog.destroy()
                else:
                    messagebox.showerror("错误", f"质押代币失败")
            except ValueError:
                messagebox.showerror("错误", "请输入有效的质押金额")
        
        ttk.Button(btn_frame, text="质押", command=on_stake).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=stake_dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
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



    # 在 WalletGUI 类中添加以下方法

    def toggle_tendermint(self):
        """切换Tendermint共识状态"""
        if not self.node:
            messagebox.showerror("错误", "请先启动本地节点")
            return
        
        if self.node.use_tendermint:
            # 禁用Tendermint
            self.node.disable_tendermint()
            self.tendermint_status_var.set("未启用")
            self.tendermint_btn.config(text="启用Tendermint")
            messagebox.showinfo("成功", "已禁用Tendermint共识")
        else:
            # 启用Tendermint
            self.node.enable_tendermint()
            self.tendermint_status_var.set("已启用")
            self.tendermint_btn.config(text="禁用Tendermint")
            messagebox.showinfo("成功", "已启用Tendermint共识")

    # 修改 update_blockchain_info 方法，添加Tendermint状态

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
        
        # 添加Tendermint状态
        tendermint_status = "未启用"
        if self.node.use_tendermint and self.node.tendermint_consensus:
            tendermint_status = f"已启用 (高度: {self.node.tendermint_consensus.current_height}, 轮次: {self.node.tendermint_consensus.current_round}, 阶段: {self.node.tendermint_consensus.current_step})"
            self.tendermint_status_var.set("已启用")
            self.tendermint_btn.config(text="禁用Tendermint")
        else:
            self.tendermint_status_var.set("未启用")
            self.tendermint_btn.config(text="启用Tendermint")
        
        self.blockchain_info_var.set(
            f"链长度: {info['chain_length']}\n"
            f"待处理交易: {info['pending_transactions']}\n"
            f"链是否有效: {info['is_valid']}\n"
            f"最新区块时间: {latest_block_time}\n"
            f"Tendermint: {tendermint_status}"
        )
        
if __name__ == "__main__":
    root = tk.Tk()
    app = WalletGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()