"""
第一轮全流程爬取测试
测试城市: New York (美国)
测试商品: restaurant

本测试脚本用于验证数据采集系统的完整流程，包括：
1. 数据验证组件（EmailValidator, PhoneValidator, URLValidator）
2. 数据去重组件（DataDeduplicator）
3. 批量处理组件（BatchProcessor）
4. 智能等待策略（SmartWaitStrategy）
5. 请求限流器（RateLimiter）
6. 数据库操作
7. 数据完整性验证

**Feature: data-collection-optimization**
**Requirements: All**
"""
import pytest
import sys
import os
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIntegrationRound1:
    """第一轮全流程集成测试"""
    
    # 测试配置
    TEST_CITY = "New York"
    TEST_PRODUCT = "restaurant"
    TEST_LIMIT = 10  # 测试时使用较小的数量
    
    def test_01_validators_integration(self):
        """测试验证器组件集成"""
        from validators.email_validator import EmailValidator
        from validators.phone_validator import PhoneValidator
        from validators.url_validator import URLValidator
        
        # 邮箱验证器
        email_validator = EmailValidator()
        
        # 有效邮箱
        valid_result = email_validator.validate("test@example.com")
        assert valid_result.is_valid, "有效邮箱应该通过验证"
        
        # 无效邮箱（图片扩展名）
        invalid_result = email_validator.validate("logo.png@example.com")
        assert not invalid_result.is_valid, "包含图片扩展名的邮箱应该被拒绝"
        
        # 电话验证器
        phone_validator = PhoneValidator()
        assert phone_validator.validate("1234567890"), "10位数字电话应该有效"
        assert not phone_validator.validate("123"), "3位数字电话应该无效"
        
        # URL验证器
        url_validator = URLValidator()
        assert url_validator.validate("https://example.com"), "有效URL应该通过格式验证"
        assert not url_validator.validate("not-a-url"), "无效URL应该被拒绝"
        
        print("✓ 验证器组件集成测试通过")
    
    def test_02_deduplicator_integration(self):
        """测试去重器组件集成"""
        from utils.data_deduplicator import DataDeduplicator
        from models.business_record import BusinessRecord
        
        deduplicator = DataDeduplicator()
        
        # 创建测试记录
        record1 = BusinessRecord(
            name="Test Business",
            email="test@example.com",
            website="https://example.com"
        )
        
        record2 = BusinessRecord(
            name="Test Business Updated",
            email="test@example.com",
            website="https://example.com",
            phones=["1234567890"]
        )
        
        # 检测重复
        existing = [record1]
        duplicate = deduplicator.check_duplicate(record2, existing)
        assert duplicate is not None, "应该检测到重复记录"
        
        # 合并记录
        merged = deduplicator.merge_records(record1, record2)
        assert merged.phones == ["1234567890"], "合并后应该保留电话信息"
        
        print("✓ 去重器组件集成测试通过")
    
    def test_03_batch_processor_integration(self):
        """测试批量处理器组件集成"""
        from utils.batch_processor import BatchProcessor
        from models.business_record import BusinessRecord
        
        # 使用回调函数来模拟数据库操作
        flushed_records = []
        def flush_callback(records):
            flushed_records.extend(records)
            return len(records)
        
        processor = BatchProcessor(batch_size=5, flush_callback=flush_callback)
        
        # 添加4条记录
        for i in range(4):
            record = BusinessRecord(name=f"Business {i}")
            processor.add(record)
        
        # 4条记录不应该触发刷新
        assert processor.get_buffer_size() == 4, "缓冲区应该有4条记录"
        assert len(flushed_records) == 0, "4条记录不应该触发刷新"
        
        # 添加第5条，应该触发刷新
        processor.add(BusinessRecord(name="Business 4"))
        assert len(flushed_records) == 5, "5条记录应该触发刷新"
        assert processor.get_buffer_size() == 0, "刷新后缓冲区应该为空"
        
        print("✓ 批量处理器组件集成测试通过")
    
    def test_04_smart_wait_integration(self):
        """测试智能等待策略组件集成"""
        from utils.smart_wait import SmartWaitStrategy
        
        strategy = SmartWaitStrategy()
        
        # 测试指数退避计算
        delay0 = strategy.calculate_backoff_delay(0)
        delay1 = strategy.calculate_backoff_delay(1)
        delay2 = strategy.calculate_backoff_delay(2)
        
        assert delay0 == 0.1, f"第0次重试延迟应该是0.1秒，实际: {delay0}"
        assert delay1 == 0.2, f"第1次重试延迟应该是0.2秒，实际: {delay1}"
        assert delay2 == 0.4, f"第2次重试延迟应该是0.4秒，实际: {delay2}"
        
        print("✓ 智能等待策略组件集成测试通过")
    
    def test_05_rate_limiter_integration(self):
        """测试请求限流器组件集成"""
        from utils.rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        
        # 测试User-Agent轮换
        ua1 = limiter.get_next_user_agent()
        ua2 = limiter.get_next_user_agent()
        
        assert ua1 is not None, "应该返回User-Agent"
        assert ua2 is not None, "应该返回User-Agent"
        
        # 测试随机化延迟
        delay = limiter.get_randomized_delay()
        base = limiter.MIN_INTERVAL
        min_delay = base * 0.7
        max_delay = base * 1.3
        
        assert min_delay <= delay <= max_delay, f"延迟应该在 {min_delay}-{max_delay} 范围内，实际: {delay}"
        
        print("✓ 请求限流器组件集成测试通过")
    
    def test_06_database_integration(self):
        """测试数据库操作集成"""
        import db as db_module
        
        # 测试数据库连接
        conn = db_module.get_db_connection()
        assert conn is not None, "应该能够获取数据库连接"
        db_module.release_connection(conn)
        
        # 测试保存和查询
        test_data = [{
            'name': 'Integration Test Business',
            'website': 'https://test.example.com',
            'emails': ['integration_test@example.com'],
            'phones': ['1234567890'],
            'city': self.TEST_CITY
        }]
        
        # 保存数据
        db_module.save_business_data_to_db(test_data)
        
        # 查询数据
        records, total = db_module.get_history_records(1, 10, 'Integration Test')
        assert total >= 1, "应该能查询到测试数据"
        
        print("✓ 数据库操作集成测试通过")
    
    def test_07_business_record_serialization(self):
        """测试商家记录序列化"""
        from models.business_record import BusinessRecord
        
        record = BusinessRecord(
            name="Test Business",
            website="https://example.com",
            email="test@example.com",
            phones=["1234567890"],
            city=self.TEST_CITY
        )
        
        # 序列化
        json_str = record.to_json()
        assert json_str is not None, "应该能序列化为JSON"
        
        # 反序列化
        restored = BusinessRecord.from_json(json_str)
        assert restored.name == record.name, "反序列化后名称应该一致"
        assert restored.city == record.city, "反序列化后城市应该一致"
        
        print("✓ 商家记录序列化测试通过")
    
    def test_08_data_integrity_validator(self):
        """测试数据完整性验证器"""
        from utils.data_integrity_validator import DataIntegrityValidator
        
        validator = DataIntegrityValidator(expected_count=10)
        
        # 创建测试数据
        test_records = []
        for i in range(8):
            test_records.append({
                'name': f'Business {i}',
                'website': f'https://business{i}.com',
                'email': f'contact{i}@business{i}.com',
                'phones': ['1234567890'],
                'city': self.TEST_CITY
            })
        
        # 验证
        report = validator.validate_extraction(test_records)
        
        assert report.actual_count == 8, f"实际数量应该是8，实际: {report.actual_count}"
        assert report.expected_count == 10, f"期望数量应该是10，实际: {report.expected_count}"
        assert 0 <= report.quality_score <= 100, f"质量评分应该在0-100之间，实际: {report.quality_score}"
        
        print(f"✓ 数据完整性验证器测试通过 (质量评分: {report.quality_score:.1f})")
    
    def test_09_structured_logger(self):
        """测试结构化日志器"""
        from utils.structured_logger import StructuredLogger
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = StructuredLogger(log_dir=tmpdir)
            
            # 记录请求
            logger.log_request("https://example.com", 200, 100.5)
            
            # 记录提取
            logger.log_extraction("https://example.com", 5, 50.0)
            
            # 记录错误 - 使用正确的接口
            logger.log_error("https://example.com", "Test error", "NETWORK")
            
            # 生成报告
            report = logger.generate_report()
            
            # 报告结构是 {'summary': {...}, 'errors_by_type': {...}, 'timestamp': ...}
            assert 'summary' in report, "报告应该包含summary"
            assert 'total_requests' in report['summary'], "报告应该包含总请求数"
            assert 'total_extractions' in report['summary'], "报告应该包含总提取数"
            assert 'total_errors' in report['summary'], "报告应该包含总错误数"
            assert 'errors_by_type' in report, "报告应该包含错误分类"
        
        print("✓ 结构化日志器测试通过")
    
    def test_10_country_city_mapping(self):
        """测试国家城市映射"""
        from models.country_city_mapping import CountryCityMapping
        
        # 创建映射
        mapping = CountryCityMapping(countries={
            "US": ["New York", "Los Angeles", "Chicago"],
            "UK": ["London", "Manchester", "Birmingham"]
        })
        
        # 序列化
        json_str = mapping.to_json()
        assert json_str is not None, "应该能序列化为JSON"
        
        # 反序列化
        restored = CountryCityMapping.from_json(json_str)
        assert restored.get_cities("US") == ["New York", "Los Angeles", "Chicago"], "反序列化后城市列表应该一致"
        
        print("✓ 国家城市映射测试通过")


class TestManualIntegrationProcedure:
    """
    手动集成测试流程文档
    
    以下测试需要手动执行，因为它们需要：
    1. 真实的Chrome浏览器
    2. 网络访问Google Maps
    3. 人工观察和验证
    """
    
    @pytest.mark.skip(reason="需要手动执行 - 启动应用服务器")
    def test_manual_01_start_server(self):
        """
        手动步骤1: 启动应用服务器
        
        执行命令: python app.py
        
        预期结果:
        - 服务器在 http://localhost:5000 启动
        - 控制台显示 "数据库初始化完成"
        """
        pass
    
    @pytest.mark.skip(reason="需要手动执行 - 登录系统")
    def test_manual_02_login(self):
        """
        手动步骤2: 登录系统
        
        1. 打开浏览器访问 http://localhost:5000
        2. 输入用户名: admin
        3. 输入密码: V000000008954
        4. 点击登录
        
        预期结果:
        - 成功跳转到操作页面
        """
        pass
    
    @pytest.mark.skip(reason="需要手动执行 - 选择城市和商品")
    def test_manual_03_select_city_product(self):
        """
        手动步骤3: 选择测试城市和商品
        
        测试配置:
        - 国家: United States (US)
        - 城市: New York
        - 商品: restaurant
        - 数量限制: 10
        
        预期结果:
        - 城市下拉框正确显示城市列表
        - 可以选择城市和输入商品名称
        """
        pass
    
    @pytest.mark.skip(reason="需要手动执行 - 执行爬取")
    def test_manual_04_execute_scraping(self):
        """
        手动步骤4: 执行爬取
        
        1. 点击"开始爬取"按钮
        2. 观察进度条和日志输出
        
        预期结果:
        - 浏览器自动打开并导航到Google Maps
        - 搜索城市和商品
        - 滚动加载商家列表
        - 提取商家信息
        - 进度条正确更新
        - WebSocket实时推送进度
        """
        pass
    
    @pytest.mark.skip(reason="需要手动执行 - 验证结果")
    def test_manual_05_verify_results(self):
        """
        手动步骤5: 验证爬取结果
        
        检查项:
        1. 数据数量是否达到预期
        2. 数据字段是否完整（name, website, city）
        3. 数据是否保存到数据库
        4. Excel导出是否正常
        5. 历史记录页面是否显示数据
        
        预期结果:
        - 提取到约10条商家数据
        - 每条数据包含商家名称
        - city字段为"New York"
        - 数据库中有对应记录
        """
        pass


def generate_test_report():
    """生成测试报告"""
    report = {
        "test_round": 1,
        "test_date": datetime.now().isoformat(),
        "test_city": "New York",
        "test_product": "restaurant",
        "test_limit": 10,
        "automated_tests": {
            "validators_integration": "待执行",
            "deduplicator_integration": "待执行",
            "batch_processor_integration": "待执行",
            "smart_wait_integration": "待执行",
            "rate_limiter_integration": "待执行",
            "database_integration": "待执行",
            "business_record_serialization": "待执行",
            "data_integrity_validator": "待执行",
            "structured_logger": "待执行",
            "country_city_mapping": "待执行"
        },
        "manual_tests": {
            "start_server": "待执行",
            "login": "待执行",
            "select_city_product": "待执行",
            "execute_scraping": "待执行",
            "verify_results": "待执行"
        },
        "issues_found": [],
        "notes": ""
    }
    
    return report


if __name__ == "__main__":
    # 生成测试报告模板
    report = generate_test_report()
    
    report_path = os.path.join(
        os.path.dirname(__file__), 
        f"integration_test_report_round1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"测试报告模板已生成: {report_path}")
    print("\n运行自动化测试: pytest tests/test_integration_round1.py -v")
