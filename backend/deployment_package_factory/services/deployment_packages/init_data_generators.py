"""生产级初始化脚本增强 - 补充默认数据和完整的表结构"""
from __future__ import annotations


def generate_default_iam_data() -> str:
    """生成 IAM 默认数据（管理员用户、默认角色）"""
    return """
-- ============================================================================
-- IAM 默认数据初始化
-- ============================================================================

-- 默认管理员用户（密码：Admin@123，需要在生产环境中修改）
INSERT INTO iam.users (id, username, email, password_hash, display_name, is_active)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'admin',
  'admin@example.com',
  '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLaEgj5u',  -- Admin@123
  '系统管理员',
  TRUE
) ON CONFLICT (username) DO NOTHING;

-- 默认角色
INSERT INTO iam.roles (id, name, description, permissions)
VALUES
  (
    '00000000-0000-0000-0000-000000000001',
    'admin',
    '系统管理员',
    '["*"]'::JSONB
  ),
  (
    '00000000-0000-0000-0000-000000000002',
    'user',
    '普通用户',
    '["read"]'::JSONB
  ),
  (
    '00000000-0000-0000-0000-000000000003',
    'developer',
    '开发者',
    '["read", "write", "deploy"]'::JSONB
  )
ON CONFLICT (name) DO NOTHING;

-- 分配管理员角色给默认管理员用户
INSERT INTO iam.user_roles (user_id, role_id)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (user_id, role_id) DO NOTHING;

-- 默认会话表
CREATE TABLE IF NOT EXISTS iam.sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES iam.users(id) ON DELETE CASCADE,
  token VARCHAR(512) UNIQUE NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON iam.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON iam.sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON iam.sessions(expires_at);
"""


def generate_gateway_default_data() -> str:
    """生成网关默认配置数据"""
    return """
-- ============================================================================
-- Gateway 默认配置数据
-- ============================================================================

-- 默认路由规则（示例）
INSERT INTO gateway.routes (id, service_name, path_pattern, target_url, method, is_active)
VALUES
  (
    '00000000-0000-0000-0000-000000000001',
    'iam',
    '/api/auth/*',
    'http://iam-service:8080',
    'ANY',
    TRUE
  ),
  (
    '00000000-0000-0000-0000-000000000002',
    'api-gateway',
    '/api/*',
    'http://api-gateway:8080',
    'ANY',
    TRUE
  )
ON CONFLICT (id) DO NOTHING;

-- 默认过滤器（认证、限流等）
INSERT INTO gateway.filters (id, route_id, filter_type, config, order_index, is_active)
VALUES
  (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    'auth',
    '{"required": true}'::JSONB,
    1,
    TRUE
  ),
  (
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    'rate_limit',
    '{"requests_per_minute": 100}'::JSONB,
    2,
    TRUE
  )
ON CONFLICT (id) DO NOTHING;
"""


def generate_monitoring_tables() -> str:
    """生成监控相关表结构"""
    return """
-- ============================================================================
-- 监控和指标表
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS monitoring;

-- 服务健康检查记录
CREATE TABLE IF NOT EXISTS monitoring.health_checks (
  id BIGSERIAL PRIMARY KEY,
  service_name VARCHAR(255) NOT NULL,
  status VARCHAR(50) NOT NULL,  -- healthy, unhealthy, degraded
  response_time_ms INTEGER,
  error_message TEXT,
  checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_health_checks_service ON monitoring.health_checks(service_name);
CREATE INDEX IF NOT EXISTS idx_health_checks_checked_at ON monitoring.health_checks(checked_at);

-- 性能指标
CREATE TABLE IF NOT EXISTS monitoring.metrics (
  id BIGSERIAL PRIMARY KEY,
  metric_name VARCHAR(255) NOT NULL,
  metric_value DOUBLE PRECISION NOT NULL,
  labels JSONB DEFAULT '{}'::JSONB,
  recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metrics_name ON monitoring.metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_recorded_at ON monitoring.metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_metrics_labels ON monitoring.metrics USING GIN(labels);
"""


def generate_workflow_tables() -> str:
    """生成工作流相关表结构（如果使用 Camunda）"""
    return """
-- ============================================================================
-- 工作流辅助表（Camunda 之外的业务工作流状态）
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS workflow;

-- 工作流实例
CREATE TABLE IF NOT EXISTS workflow.instances (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  process_key VARCHAR(255) NOT NULL,
  business_key VARCHAR(255),
  status VARCHAR(50) NOT NULL,  -- running, completed, failed, canceled
  variables JSONB DEFAULT '{}'::JSONB,
  started_by VARCHAR(255),
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_workflow_instances_process_key ON workflow.instances(process_key);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_business_key ON workflow.instances(business_key);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_status ON workflow.instances(status);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_started_at ON workflow.instances(started_at);

-- 工作流任务
CREATE TABLE IF NOT EXISTS workflow.tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  instance_id UUID NOT NULL REFERENCES workflow.instances(id) ON DELETE CASCADE,
  task_key VARCHAR(255) NOT NULL,
  assignee VARCHAR(255),
  status VARCHAR(50) NOT NULL,  -- pending, in_progress, completed, failed
  variables JSONB DEFAULT '{}'::JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflow_tasks_instance_id ON workflow.tasks(instance_id);
CREATE INDEX IF NOT EXISTS idx_workflow_tasks_assignee ON workflow.tasks(assignee);
CREATE INDEX IF NOT EXISTS idx_workflow_tasks_status ON workflow.tasks(status);
"""


def generate_document_tables() -> str:
    """生成文档管理相关表结构"""
    return """
-- ============================================================================
-- 文档管理表
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS documents;

-- 文档元数据
CREATE TABLE IF NOT EXISTS documents.metadata (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename VARCHAR(512) NOT NULL,
  original_filename VARCHAR(512) NOT NULL,
  mime_type VARCHAR(255),
  size_bytes BIGINT NOT NULL,
  storage_path VARCHAR(1024) NOT NULL,  -- MinIO bucket + key
  checksum VARCHAR(64),  -- SHA256
  owner VARCHAR(255),
  tags JSONB DEFAULT '[]'::JSONB,
  metadata JSONB DEFAULT '{}'::JSONB,
  is_deleted BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents.metadata(filename);
CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents.metadata(owner);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents.metadata(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_is_deleted ON documents.metadata(is_deleted);
CREATE INDEX IF NOT EXISTS idx_documents_tags ON documents.metadata USING GIN(tags);

-- 文档版本历史
CREATE TABLE IF NOT EXISTS documents.versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES documents.metadata(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL,
  storage_path VARCHAR(1024) NOT NULL,
  size_bytes BIGINT NOT NULL,
  checksum VARCHAR(64),
  modified_by VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(document_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_documents_versions_document_id ON documents.versions(document_id);
"""


def generate_notification_tables() -> str:
    """生成通知系统表结构"""
    return """
-- ============================================================================
-- 通知系统表
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS notifications;

-- 通知记录
CREATE TABLE IF NOT EXISTS notifications.messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recipient VARCHAR(255) NOT NULL,
  subject VARCHAR(512),
  body TEXT NOT NULL,
  notification_type VARCHAR(50) NOT NULL,  -- email, sms, push, in_app
  priority VARCHAR(50) DEFAULT 'normal',  -- low, normal, high, urgent
  status VARCHAR(50) NOT NULL,  -- pending, sent, failed, read
  metadata JSONB DEFAULT '{}'::JSONB,
  sent_at TIMESTAMP,
  read_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications.messages(recipient);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications.messages(status);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications.messages(created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications.messages(notification_type);
"""


def generate_cache_tables() -> str:
    """生成缓存辅助表（用于分布式缓存的持久化备份）"""
    return """
-- ============================================================================
-- 缓存辅助表（持久化备份）
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS cache;

-- 缓存条目
CREATE TABLE IF NOT EXISTS cache.entries (
  cache_key VARCHAR(512) PRIMARY KEY,
  cache_value TEXT NOT NULL,
  namespace VARCHAR(255) DEFAULT 'default',
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cache_namespace ON cache.entries(namespace);
CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON cache.entries(expires_at);

-- 清理过期缓存的函数
CREATE OR REPLACE FUNCTION cache.cleanup_expired_entries()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM cache.entries
  WHERE expires_at IS NOT NULL AND expires_at < NOW();
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
"""


def generate_job_queue_tables() -> str:
    """生成任务队列表结构"""
    return """
-- ============================================================================
-- 任务队列表
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS jobs;

-- 异步任务
CREATE TABLE IF NOT EXISTS jobs.tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type VARCHAR(255) NOT NULL,
  payload JSONB NOT NULL,
  status VARCHAR(50) NOT NULL,  -- pending, running, completed, failed, canceled
  priority INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  retry_count INTEGER DEFAULT 0,
  worker_id VARCHAR(255),
  result JSONB,
  error_message TEXT,
  scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  next_retry_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs.tasks(status);
CREATE INDEX IF NOT EXISTS idx_jobs_task_type ON jobs.tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_jobs_scheduled_at ON jobs.tasks(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_jobs_next_retry_at ON jobs.tasks(next_retry_at);
CREATE INDEX IF NOT EXISTS idx_jobs_worker_id ON jobs.tasks(worker_id);

-- 任务锁（防止重复执行）
CREATE TABLE IF NOT EXISTS jobs.locks (
  lock_key VARCHAR(512) PRIMARY KEY,
  worker_id VARCHAR(255) NOT NULL,
  acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_locks_expires_at ON jobs.locks(expires_at);
"""
