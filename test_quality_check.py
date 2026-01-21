#!/usr/bin/env python3
"""
静态代码质量验证脚本 - 不依赖外部模块，直接检查源代码
"""
import os
import re
import ast


def check_file_syntax(filepath):
    """检查 Python 文件语法"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def check_progress_manager_thread_safety():
    """验证 ProgressManager 是否添加了线程锁"""
    print("\n" + "=" * 60)
    print("1. ProgressManager 线程安全验证")
    print("=" * 60)
    
    with open('scraper.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('self._lock', '线程锁属性'),
        ('with self._lock:', '锁的使用'),
        ('os.replace(temp_file, progress_file)', '原子文件替换'),
        ('线程安全', '文档说明'),
    ]
    
    all_passed = True
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✅ 包含: {desc}")
        else:
            print(f"  ❌ 缺少: {desc}")
            all_passed = False
    
    return all_passed


def check_deduplicator_initialization():
    """验证 DataDeduplicator 不再重复初始化"""
    print("\n" + "=" * 60)
    print("2. DataDeduplicator 初始化验证")
    print("=" * 60)
    
    with open('contact_scraper.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    count = content.count('_deduplicator = DataDeduplicator()')
    
    if count == 1:
        print(f"  ✅ DataDeduplicator 只初始化 1 次")
        return True
    else:
        print(f"  ❌ DataDeduplicator 初始化了 {count} 次")
        return False


def check_scraper_service_error_handling():
    """验证 ScraperService 资源清理改进"""
    print("\n" + "=" * 60)
    print("3. ScraperService 资源清理验证")
    print("=" * 60)
    
    with open('services/scraper_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('_logger.error', '错误日志记录'),
        ('pkill', '进程清理命令'),
        ('driver_quit_failed', '驱动退出失败上下文'),
        ('from utils.enterprise_logger import get_logger', 'logger 导入'),
    ]
    
    all_passed = True
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✅ 包含: {desc}")
        else:
            print(f"  ❌ 缺少: {desc}")
            all_passed = False
    
    return all_passed


def check_cdp_exception_handling():
    """验证 wait_for_network_idle 的 CDP 异常处理"""
    print("\n" + "=" * 60)
    print("4. CDP 异常处理验证")
    print("=" * 60)
    
    # 逻辑已在重构中移至 utils/selenium_helpers.py
    filepath = 'utils/selenium_helpers.py'
    if not os.path.exists(filepath):
        print(f"  ❌ 找不到文件: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('WebDriverException', 'WebDriver 异常类'),
        ('from selenium.common.exceptions import WebDriverException', '异常导入'),
        ('except WebDriverException:', '捕获 CDP 异常'),
        ('wait_for_page_load(driver, timeout)', '回退到页面加载等待'),
    ]
    
    all_passed = True
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✅ 包含: {desc}")
        else:
            print(f"  ❌ 缺少: {desc}")
            all_passed = False
    
    return all_passed


def check_history_manager_connection_pool():
    """验证 HistoryManager 使用连接池"""
    print("\n" + "=" * 60)
    print("5. HistoryManager 连接池验证")
    print("=" * 60)
    
    with open('utils/history_manager.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('from db import get_connection, get_db_connection, release_connection', '连接池导入'),
        ('get_db_connection()', '获取连接调用'),
        ('release_connection(', '释放连接调用'),
    ]
    
    # 检查不应该存在的内容
    bad_patterns = [
        ('sqlite3.connect', '直接 sqlite3 连接'),
        ('self._get_connection()', '旧的连接方法'),
    ]
    
    all_passed = True
    
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✅ 包含: {desc}")
        else:
            print(f"  ❌ 缺少: {desc}")
            all_passed = False
    
    for keyword, desc in bad_patterns:
        if keyword in content:
            print(f"  ❌ 不应包含: {desc}")
            all_passed = False
        else:
            print(f"  ✅ 已移除: {desc}")
    
    return all_passed


def check_xss_protection():
    """验证 XSS 防护函数"""
    print("\n" + "=" * 60)
    print("6. XSS 防护验证")
    print("=" * 60)
    
    with open('templates/operation.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('function escapeHtml(', 'HTML 转义函数'),
        ('function escapeUrl(', 'URL 转义函数'),
        ('escapeHtml(b.name', '商家名称转义'),
        ('escapeUrl(b.website)', '网站 URL 转义'),
        ('rel="noopener noreferrer"', 'noopener 安全属性'),
    ]
    
    all_passed = True
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✅ 包含: {desc}")
        else:
            print(f"  ❌ 缺少: {desc}")
            all_passed = False
    
    return all_passed


def check_session_security():
    """验证 Session 安全配置"""
    print("\n" + "=" * 60)
    print("7. Session 安全配置验证")
    print("=" * 60)
    
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('SESSION_COOKIE_HTTPONLY', 'HttpOnly Cookie'),
        ('SESSION_COOKIE_SAMESITE', 'SameSite Cookie'),
        ('from utils.auth import login_required', 'login_required 导入'),
    ]
    
    all_passed = True
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✅ 包含: {desc}")
        else:
            print(f"  ❌ 缺少: {desc}")
            all_passed = False
    
    return all_passed


def check_syntax_all_files():
    """检查所有修改文件的语法"""
    print("\n" + "=" * 60)
    print("8. 语法检查")
    print("=" * 60)
    
    files = [
        'app.py',
        'scraper.py',
        'contact_scraper.py',
        'services/scraper_service.py',
        'utils/history_manager.py',
        'utils/auth.py',
        'db.py',
    ]
    
    all_passed = True
    for filepath in files:
        passed, error = check_file_syntax(filepath)
        if passed:
            print(f"  ✅ {filepath}")
        else:
            print(f"  ❌ {filepath}: {error}")
            all_passed = False
    
    return all_passed


def main():
    """运行所有静态检查"""
    print("\n" + "=" * 60)
    print("         静态代码质量验证")
    print("=" * 60)
    
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    results = []
    
    results.append(("语法检查", check_syntax_all_files()))
    results.append(("ProgressManager 线程安全", check_progress_manager_thread_safety()))
    results.append(("DataDeduplicator 初始化", check_deduplicator_initialization()))
    results.append(("ScraperService 资源清理", check_scraper_service_error_handling()))
    results.append(("CDP 异常处理", check_cdp_exception_handling()))
    results.append(("HistoryManager 连接池", check_history_manager_connection_pool()))
    results.append(("XSS 防护", check_xss_protection()))
    results.append(("Session 安全", check_session_security()))
    
    print("\n" + "=" * 60)
    print("         测试结果汇总")
    print("=" * 60)
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status}: {name}")
    
    print("=" * 60)
    print(f"通过率: {passed_count}/{total_count} ({passed_count*100//total_count}%)")
    
    if passed_count == total_count:
        print("🎉 所有检查通过！代码质量验证成功。")
        return 0
    else:
        print("⚠️ 部分检查失败，请检查上述错误。")
        return 1


if __name__ == '__main__':
    exit(main())
