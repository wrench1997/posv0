import os
import argparse

def count_lines_in_file(file_path):
    """统计单个文件的行数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return sum(1 for _ in file)
    except Exception as e:
        print(f"无法读取文件 {file_path}: {e}")
        return 0

def count_lines_in_directory(directory, extensions=None, exclude_dirs=None):
    """
    递归统计目录中指定扩展名文件的总行数
    
    参数:
    directory (str): 要统计的目录路径
    extensions (list): 要统计的文件扩展名列表，默认为['.py']
    exclude_dirs (list): 要排除的目录名列表
    
    返回:
    tuple: (总行数, 文件数量, 详细统计信息字典)
    """
    if extensions is None:
        extensions = ['.py']
    if exclude_dirs is None:
        exclude_dirs = ['.git', '.venv', 'venv', '__pycache__', 'node_modules']
    
    total_lines = 0
    total_files = 0
    stats = {}
    
    for root, dirs, files in os.walk(directory):
        # 排除指定目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                lines = count_lines_in_file(file_path)
                
                # 更新统计信息
                rel_path = os.path.relpath(file_path, directory)
                stats[rel_path] = lines
                total_lines += lines
                total_files += 1
    
    return total_lines, total_files, stats

def main():
    parser = argparse.ArgumentParser(description='统计代码行数')
    parser.add_argument('directory', nargs='?', default='.', 
                        help='要统计的目录路径 (默认为当前目录)')
    parser.add_argument('-e', '--extensions', nargs='+', default=['.py'],
                        help='要统计的文件扩展名 (默认为 .py)')
    parser.add_argument('-x', '--exclude', nargs='+', 
                        default=['.git', '.venv', 'venv', '__pycache__', 'node_modules'],
                        help='要排除的目录名')
    parser.add_argument('-d', '--detail', action='store_true',
                        help='显示每个文件的详细行数')
    
    args = parser.parse_args()
    
    print(f"正在统计 {args.directory} 中的 {', '.join(args.extensions)} 文件...")
    total_lines, total_files, stats = count_lines_in_directory(
        args.directory, args.extensions, args.exclude
    )
    
    print(f"\n总计: {total_lines} 行代码，分布在 {total_files} 个文件中")
    
    if args.detail and stats:
        print("\n详细统计:")
        # 按行数降序排列
        for file_path, lines in sorted(stats.items(), key=lambda x: x[1], reverse=True):
            print(f"{lines:6d} 行: {file_path}")

if __name__ == "__main__":
    main()
