-- EAM Seed Data for PostgreSQL
-- This script is idempotent and can be executed multiple times.

-- Insert default asset types
INSERT INTO eam_schema.asset_types (id, name, code, description, is_active, created_at)
VALUES
  (gen_random_uuid(), '生产设备', 'PRODUCTION_EQUIPMENT', '用于生产线的核心设备', TRUE, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '检测仪器', 'INSPECTION_INSTRUMENT', '质量检测和测量仪器', TRUE, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '运输工具', 'TRANSPORT_VEHICLE', '厂内物流运输工具', TRUE, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '辅助设施', 'AUXILIARY_FACILITY', '水电气等辅助设施', TRUE, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;

-- Insert default maintenance types
INSERT INTO eam_schema.maintenance_types (id, name, code, priority, estimated_hours, created_at)
VALUES
  (gen_random_uuid(), '紧急维修', 'EMERGENCY', 1, 2.0, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '计划性维修', 'PLANNED', 3, 8.0, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '预防性维护', 'PREVENTIVE', 4, 4.0, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '故障维修', 'CORRECTIVE', 2, 6.0, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;

-- Insert default work order statuses
INSERT INTO eam_schema.work_order_statuses (id, name, code, sequence, is_terminal, created_at)
VALUES
  (gen_random_uuid(), '待审核', 'PENDING_REVIEW', 1, FALSE, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '已批准', 'APPROVED', 2, FALSE, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '执行中', 'IN_PROGRESS', 3, FALSE, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '待验收', 'PENDING_VERIFICATION', 4, FALSE, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '已完成', 'COMPLETED', 5, TRUE, CURRENT_TIMESTAMP),
  (gen_random_uuid(), '已取消', 'CANCELLED', 6, TRUE, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;

-- Insert default permission resources for EAM module
INSERT INTO iam.permissions (id, resource_key, resource_name, actions, module, created_at)
VALUES
  (gen_random_uuid(), 'eam.asset', '资产管理', ARRAY['view', 'create', 'update', 'delete'], 'eam', CURRENT_TIMESTAMP),
  (gen_random_uuid(), 'eam.workorder', '工单管理', ARRAY['view', 'create', 'update', 'approve', 'execute', 'verify'], 'eam', CURRENT_TIMESTAMP),
  (gen_random_uuid(), 'eam.maintenance', '维护计划', ARRAY['view', 'create', 'update', 'delete'], 'eam', CURRENT_TIMESTAMP),
  (gen_random_uuid(), 'eam.spare_parts', '备件管理', ARRAY['view', 'create', 'update', 'allocate'], 'eam', CURRENT_TIMESTAMP),
  (gen_random_uuid(), 'eam.report', 'EAM报表', ARRAY['view', 'export'], 'eam', CURRENT_TIMESTAMP)
ON CONFLICT (resource_key) DO NOTHING;

-- Create EAM default roles
DO $$
DECLARE
  v_manager_role_id UUID;
  v_technician_role_id UUID;
  v_inspector_role_id UUID;
BEGIN
  -- EAM Manager Role
  INSERT INTO iam.roles (id, name, description, created_at)
  VALUES (gen_random_uuid(), 'EAM管理员', 'EAM模块管理员，具有所有权限', CURRENT_TIMESTAMP)
  ON CONFLICT (name) DO NOTHING
  RETURNING id INTO v_manager_role_id;

  -- EAM Technician Role
  INSERT INTO iam.roles (id, name, description, created_at)
  VALUES (gen_random_uuid(), 'EAM维修技师', 'EAM维修执行人员', CURRENT_TIMESTAMP)
  ON CONFLICT (name) DO NOTHING
  RETURNING id INTO v_technician_role_id;

  -- EAM Inspector Role
  INSERT INTO iam.roles (id, name, description, created_at)
  VALUES (gen_random_uuid(), 'EAM质检员', 'EAM维修验收人员', CURRENT_TIMESTAMP)
  ON CONFLICT (name) DO NOTHING
  RETURNING id INTO v_inspector_role_id;

  -- Assign permissions to roles (simplified example)
  IF v_manager_role_id IS NOT NULL THEN
    UPDATE iam.roles
    SET permissions = (
      SELECT jsonb_agg(jsonb_build_object('resource', resource_key, 'actions', actions))
      FROM iam.permissions
      WHERE module = 'eam'
    )
    WHERE id = v_manager_role_id;
  END IF;
END $$;

-- Create default EAM schema tables if not exist
CREATE TABLE IF NOT EXISTS eam_schema.asset_types (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  code VARCHAR(50) UNIQUE NOT NULL,
  description TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eam_schema.maintenance_types (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  code VARCHAR(50) UNIQUE NOT NULL,
  priority INTEGER DEFAULT 3,
  estimated_hours DECIMAL(10,2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eam_schema.work_order_statuses (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  code VARCHAR(50) UNIQUE NOT NULL,
  sequence INTEGER NOT NULL,
  is_terminal BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS iam.permissions (
  id UUID PRIMARY KEY,
  resource_key VARCHAR(255) UNIQUE NOT NULL,
  resource_name VARCHAR(255) NOT NULL,
  actions TEXT[] DEFAULT '{}',
  module VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_asset_types_code ON eam_schema.asset_types(code);
CREATE INDEX IF NOT EXISTS idx_maintenance_types_code ON eam_schema.maintenance_types(code);
CREATE INDEX IF NOT EXISTS idx_work_order_statuses_code ON eam_schema.work_order_statuses(code);
CREATE INDEX IF NOT EXISTS idx_permissions_module ON iam.permissions(module);
