"""测试生产级初始化脚本生成"""
import pytest

from deployment_package_factory.services.deployment_packages.init_data_generators import (
    generate_default_iam_data,
    generate_gateway_default_data,
    generate_monitoring_tables,
    generate_workflow_tables,
    generate_document_tables,
    generate_notification_tables,
    generate_cache_tables,
    generate_job_queue_tables,
)
from deployment_package_factory.services.deployment_packages.init_script_renderer import (
    render_init_files,
    _postgres_schema_sql,
)


def test_generate_default_iam_data():
    """测试生成 IAM 默认数据"""
    sql = generate_default_iam_data()

    # 验证包含关键 SQL 语句
    assert "INSERT INTO iam.users" in sql
    assert "INSERT INTO iam.roles" in sql
    assert "INSERT INTO iam.user_roles" in sql
    assert "CREATE TABLE IF NOT EXISTS iam.sessions" in sql

    # 验证默认管理员
    assert "admin" in sql
    assert "系统管理员" in sql

    # 验证默认角色
    assert "'admin'" in sql
    assert "'user'" in sql
    assert "'developer'" in sql

    # 验证幂等性
    assert "ON CONFLICT" in sql


def test_generate_gateway_default_data():
    """测试生成网关默认配置数据"""
    sql = generate_gateway_default_data()

    # 验证包含关键 SQL 语句
    assert "INSERT INTO gateway.routes" in sql
    assert "INSERT INTO gateway.filters" in sql

    # 验证默认路由
    assert "iam" in sql
    assert "api-gateway" in sql

    # 验证过滤器类型
    assert "auth" in sql
    assert "rate_limit" in sql

    # 验证幂等性
    assert "ON CONFLICT" in sql


def test_generate_monitoring_tables():
    """测试生成监控表结构"""
    sql = generate_monitoring_tables()

    # 验证 schema 创建
    assert "CREATE SCHEMA IF NOT EXISTS monitoring" in sql

    # 验证表创建
    assert "CREATE TABLE IF NOT EXISTS monitoring.health_checks" in sql
    assert "CREATE TABLE IF NOT EXISTS monitoring.metrics" in sql

    # 验证字段
    assert "service_name" in sql
    assert "metric_name" in sql
    assert "response_time_ms" in sql

    # 验证索引
    assert "CREATE INDEX" in sql


def test_generate_workflow_tables():
    """测试生成工作流表结构"""
    sql = generate_workflow_tables()

    # 验证 schema 创建
    assert "CREATE SCHEMA IF NOT EXISTS workflow" in sql

    # 验证表创建
    assert "CREATE TABLE IF NOT EXISTS workflow.instances" in sql
    assert "CREATE TABLE IF NOT EXISTS workflow.tasks" in sql

    # 验证外键关系
    assert "REFERENCES workflow.instances(id)" in sql

    # 验证状态字段
    assert "status VARCHAR(50)" in sql


def test_generate_document_tables():
    """测试生成文档管理表结构"""
    sql = generate_document_tables()

    # 验证 schema 创建
    assert "CREATE SCHEMA IF NOT EXISTS documents" in sql

    # 验证表创建
    assert "CREATE TABLE IF NOT EXISTS documents.metadata" in sql
    assert "CREATE TABLE IF NOT EXISTS documents.versions" in sql

    # 验证字段
    assert "filename" in sql
    assert "storage_path" in sql
    assert "checksum" in sql

    # 验证 JSONB 字段
    assert "JSONB" in sql


def test_generate_notification_tables():
    """测试生成通知系统表结构"""
    sql = generate_notification_tables()

    # 验证 schema 创建
    assert "CREATE SCHEMA IF NOT EXISTS notifications" in sql

    # 验证表创建
    assert "CREATE TABLE IF NOT EXISTS notifications.messages" in sql

    # 验证字段
    assert "recipient" in sql
    assert "notification_type" in sql
    assert "priority" in sql


def test_generate_cache_tables():
    """测试生成缓存表结构"""
    sql = generate_cache_tables()

    # 验证 schema 创建
    assert "CREATE SCHEMA IF NOT EXISTS cache" in sql

    # 验证表创建
    assert "CREATE TABLE IF NOT EXISTS cache.entries" in sql

    # 验证清理函数
    assert "CREATE OR REPLACE FUNCTION cache.cleanup_expired_entries()" in sql
    assert "DELETE FROM cache.entries" in sql


def test_generate_job_queue_tables():
    """测试生成任务队列表结构"""
    sql = generate_job_queue_tables()

    # 验证 schema 创建
    assert "CREATE SCHEMA IF NOT EXISTS jobs" in sql

    # 验证表创建
    assert "CREATE TABLE IF NOT EXISTS jobs.tasks" in sql
    assert "CREATE TABLE IF NOT EXISTS jobs.locks" in sql

    # 验证字段
    assert "task_type" in sql
    assert "retry_count" in sql
    assert "worker_id" in sql


def test_postgres_schema_includes_enhanced_tables():
    """测试 PostgreSQL schema 包含增强的表结构"""
    manifest = {
        "database": "postgres",
        "platformServices": ["iam", "api-gateway"],
        "businessServices": ["eam"],
        "middleware": ["minio", "qdrant"],
        "runtimeConfig": {"resources": []},
    }

    sql = _postgres_schema_sql(manifest)

    # 验证包含 IAM 核心表
    assert "CREATE TABLE IF NOT EXISTS iam.users" in sql

    # 验证包含增强的表结构
    assert "CREATE SCHEMA IF NOT EXISTS monitoring" in sql
    assert "CREATE SCHEMA IF NOT EXISTS workflow" in sql
    assert "CREATE SCHEMA IF NOT EXISTS documents" in sql
    assert "CREATE SCHEMA IF NOT EXISTS notifications" in sql
    assert "CREATE SCHEMA IF NOT EXISTS cache" in sql
    assert "CREATE SCHEMA IF NOT EXISTS jobs" in sql

    # 验证包含默认数据
    assert "INSERT INTO iam.users" in sql
    assert "INSERT INTO gateway.routes" in sql


def test_postgres_schema_is_idempotent():
    """测试 PostgreSQL schema 是幂等的"""
    manifest = {
        "database": "postgres",
        "platformServices": ["iam"],
        "businessServices": [],
        "middleware": [],
        "runtimeConfig": {"resources": []},
    }

    sql = _postgres_schema_sql(manifest)

    # 所有创建语句都应该使用 IF NOT EXISTS
    assert "CREATE SCHEMA IF NOT EXISTS" in sql
    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql

    # 所有插入语句都应该使用 ON CONFLICT
    assert "ON CONFLICT" in sql


def test_render_init_files_includes_postgres_sql():
    """测试渲染初始化文件包含 PostgreSQL SQL"""
    manifest = {
        "packageId": "test-pkg",
        "projectKey": "test",
        "database": "postgres",
        "platformServices": ["iam"],
        "businessServices": [],
        "middleware": ["minio"],
        "runtimeConfig": {"resources": []},
    }

    files = render_init_files(manifest)

    # 查找 PostgreSQL 初始化 SQL 文件
    postgres_file = next(
        (f for f in files if str(f.path) == "init/postgres/001_schema.sql"),
        None
    )

    assert postgres_file is not None
    assert "CREATE TABLE IF NOT EXISTS iam.users" in postgres_file.content
    assert "INSERT INTO iam.users" in postgres_file.content


def test_all_table_generators_return_valid_sql():
    """测试所有表生成器返回有效的 SQL"""
    generators = [
        generate_default_iam_data,
        generate_gateway_default_data,
        generate_monitoring_tables,
        generate_workflow_tables,
        generate_document_tables,
        generate_notification_tables,
        generate_cache_tables,
        generate_job_queue_tables,
    ]

    for generator in generators:
        sql = generator()

        # 验证返回的是字符串
        assert isinstance(sql, str)

        # 验证包含 SQL 关键字
        assert any(keyword in sql.upper() for keyword in ["CREATE", "INSERT", "ALTER"])

        # 验证没有明显的语法错误
        assert sql.count("(") == sql.count(")")  # 括号匹配
        assert ";" in sql  # 包含语句结束符


def test_enhanced_tables_have_indexes():
    """测试增强的表结构包含索引"""
    generators = [
        generate_monitoring_tables,
        generate_workflow_tables,
        generate_document_tables,
        generate_notification_tables,
        generate_cache_tables,
        generate_job_queue_tables,
    ]

    for generator in generators:
        sql = generator()
        assert "CREATE INDEX" in sql


def test_default_data_uses_uuids():
    """测试默认数据使用 UUID"""
    sql = generate_default_iam_data()

    # 验证使用 UUID 格式（00000000-0000-0000-0000-000000000001）
    assert "00000000-0000-0000-0000-000000000001" in sql


def test_postgres_schema_handles_empty_services():
    """测试处理空服务列表"""
    manifest = {
        "database": "postgres",
        "platformServices": [],
        "businessServices": [],
        "middleware": [],
        "runtimeConfig": {"resources": []},
    }

    sql = _postgres_schema_sql(manifest)

    # 应该仍然生成增强的表结构
    assert "CREATE SCHEMA IF NOT EXISTS monitoring" in sql
    assert "CREATE SCHEMA IF NOT EXISTS jobs" in sql


def test_postgres_schema_includes_comments():
    """测试 PostgreSQL schema 包含注释"""
    manifest = {
        "database": "postgres",
        "platformServices": ["iam"],
        "businessServices": [],
        "middleware": [],
        "runtimeConfig": {"resources": []},
    }

    sql = _postgres_schema_sql(manifest)

    # 验证包含注释
    assert "--" in sql
    assert "PostgreSQL schema" in sql
