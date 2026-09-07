# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- 新增 `image_manager.py` 模块，统一管理镜像导出功能
  - 支持 Docker、skopeo、containerd 三种导出方式
  - 提供环境检查接口 `check_image_export_environment()`
  - 提供统一导出接口 `export_images_with_runner()`
- 新增 `errors.py` 模块，提供统一错误处理机制
  - `PackageBuildError` - 包构建错误
  - `ImageExportError` - 镜像导出错误
  - `handle_build_error()` - 错误上下文管理器
- 新增单元测试：
  - `test_image_manager.py` - 镜像管理模块测试（6 个测试）
  - `test_errors.py` - 错误处理模块测试（3 个测试）
- 新增文档：
  - `backend/deployment_package_factory/services/deployment_packages/README.md` - 模块架构说明

### Changed
- 重构 `builder.py`，提取镜像导出和错误处理逻辑到独立模块
- 更新 `docs/deployment-package-factory-detailed-design.md`，添加架构改进记录

### Fixed
- 修复 `mcp_verify_renderer` 未被 builder.py 调用的问题

### Technical Debt
- 代码模块化：将超大 builder.py（2000+ 行）拆分为多个职责单一的模块
- 测试覆盖：所有新模块均有独立单元测试
- 错误处理：统一错误类型和日志格式

## [Previous Changes]

之前的变更请参考 git 提交历史。
