import React, { useEffect, useState } from "react";
import { Alert, Button, Drawer, List, message, Select, Spin, Tag, Typography } from "antd";
import { EyeOutlined, ReloadOutlined } from "@ant-design/icons";
import { previewDeploymentPackageConfig, type PackagePreviewFilesResponse, type PreviewFile } from "../../api/deploymentPackages";
import styles from "./ConfigPreviewDrawer.module.css";

const { Paragraph, Text } = Typography;

interface ConfigPreviewDrawerProps {
  taskId: string | null;
  open: boolean;
  onClose: () => void;
}

const LANGUAGE_LABELS: Record<string, string> = {
  yaml: "YAML",
  json: "JSON",
  shell: "Shell",
  sql: "SQL",
  markdown: "Markdown",
  text: "Text",
};

export const ConfigPreviewDrawer: React.FC<ConfigPreviewDrawerProps> = ({ taskId, open, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [previewData, setPreviewData] = useState<PackagePreviewFilesResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<PreviewFile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && taskId) {
      void loadPreview();
    } else {
      setPreviewData(null);
      setSelectedFile(null);
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, taskId]);

  const loadPreview = async () => {
    if (!taskId) return;

    setLoading(true);
    setError(null);

    try {
      const data = await previewDeploymentPackageConfig(taskId);
      setPreviewData(data);

      // 默认选择第一个文件
      if (data.files.length > 0) {
        setSelectedFile(data.files[0]);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "加载配置预览失败";
      setError(errorMessage);
      void message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const loadSpecificFiles = async (filePaths: string[]) => {
    if (!taskId) return;

    setLoading(true);
    setError(null);

    try {
      const data = await previewDeploymentPackageConfig(taskId, filePaths);
      setPreviewData(data);

      if (data.files.length > 0) {
        setSelectedFile(data.files[0]);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "加载配置文件失败";
      setError(errorMessage);
      void message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (file: PreviewFile) => {
    setSelectedFile(file);
  };

  const handleLoadMore = () => {
    if (!previewData) return;

    // 加载所有可用文件
    void loadSpecificFiles(previewData.availableFiles);
  };

  return (
    <Drawer
      title="配置文件预览"
      open={open}
      onClose={onClose}
      width={900}
      extra={
        <Button icon={<ReloadOutlined />} onClick={() => void loadPreview()} loading={loading}>
          刷新
        </Button>
      }
    >
      {loading && !previewData && (
        <div className={styles.loadingContainer}>
          <Spin tip="加载配置文件..." />
        </div>
      )}

      {error && (
        <Alert
          type="error"
          message="加载失败"
          description={error}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {previewData && (
        <div className={styles.previewContainer}>
          <div className={styles.fileList}>
            <div className={styles.fileListHeader}>
              <Text strong>配置文件 ({previewData.files.length})</Text>
            </div>
            <List
              size="small"
              dataSource={previewData.files}
              renderItem={(file) => (
                <List.Item
                  className={selectedFile?.path === file.path ? styles.selectedFile : ""}
                  onClick={() => handleFileSelect(file)}
                  style={{ cursor: "pointer", padding: "8px 12px" }}
                >
                  <div className={styles.fileItem}>
                    <div>
                      <EyeOutlined style={{ marginRight: 8 }} />
                      <Text ellipsis style={{ maxWidth: 200 }}>{file.path}</Text>
                    </div>
                    <div>
                      <Tag color="blue">{LANGUAGE_LABELS[file.language] || file.language}</Tag>
                      {file.truncated && <Tag color="orange">已截断</Tag>}
                    </div>
                  </div>
                </List.Item>
              )}
            />

            {previewData.availableFiles.length > previewData.files.length && (
              <Button
                type="link"
                size="small"
                onClick={handleLoadMore}
                loading={loading}
                style={{ marginTop: 8 }}
              >
                加载更多文件 ({previewData.availableFiles.length - previewData.files.length} 个)
              </Button>
            )}

            <div className={styles.availableFilesHint}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                可预览 {previewData.availableFiles.length} 个配置文件
              </Text>
            </div>
          </div>

          <div className={styles.fileContent}>
            {selectedFile ? (
              <>
                <div className={styles.fileHeader}>
                  <Text strong>{selectedFile.path}</Text>
                  <div>
                    <Tag color="blue">{LANGUAGE_LABELS[selectedFile.language] || selectedFile.language}</Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {(selectedFile.size / 1024).toFixed(2)} KB
                    </Text>
                  </div>
                </div>

                {selectedFile.truncated && (
                  <Alert
                    type="warning"
                    message="文件已被截断"
                    description="文件过大，仅显示前 500 KB 内容。下载完整部署包以查看全部内容。"
                    showIcon
                    style={{ marginBottom: 12 }}
                  />
                )}

                <pre className={styles.codeBlock}>
                  <code className={`language-${selectedFile.language}`}>
                    {selectedFile.content}
                  </code>
                </pre>
              </>
            ) : (
              <div className={styles.emptyContent}>
                <Text type="secondary">请选择一个文件进行预览</Text>
              </div>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
};
