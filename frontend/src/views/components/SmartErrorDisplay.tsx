import React, { useState } from "react";
import { Alert, Button, Collapse, Space, Typography } from "antd";
import { InfoCircleOutlined, BulbOutlined, ToolOutlined } from "@ant-design/icons";
import styles from "./SmartErrorDisplay.module.css";

const { Paragraph, Text, Link } = Typography;
const { Panel } = Collapse;

interface SmartErrorDisplayProps {
  error: string;
  style?: React.CSSProperties;
}

interface ParsedError {
  userMessage: string;
  possibleCauses: string[];
  solutions: string[];
  technicalDetails: string;
}

function parseErrorMessage(error: string): ParsedError {
  const lines = error.split("\n");

  let userMessage = "";
  const possibleCauses: string[] = [];
  const solutions: string[] = [];
  let technicalDetails = "";

  let currentSection: "user" | "causes" | "solutions" | "technical" = "user";

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith("可能原因：")) {
      currentSection = "causes";
      continue;
    } else if (trimmed.startsWith("解决方案：")) {
      currentSection = "solutions";
      continue;
    } else if (trimmed.startsWith("技术细节：")) {
      currentSection = "technical";
      technicalDetails = trimmed.replace("技术细节：", "").trim();
      continue;
    }

    if (!trimmed) continue;

    switch (currentSection) {
      case "user":
        if (!userMessage) {
          userMessage = trimmed;
        }
        break;
      case "causes":
        if (trimmed.startsWith("•")) {
          possibleCauses.push(trimmed.substring(1).trim());
        }
        break;
      case "solutions":
        // 匹配 "1. xxx" 格式
        const solutionMatch = trimmed.match(/^\d+\.\s*(.+)$/);
        if (solutionMatch) {
          solutions.push(solutionMatch[1]);
        }
        break;
      case "technical":
        technicalDetails += " " + trimmed;
        break;
    }
  }

  // 如果没有解析出结构化内容，将整个错误作为用户消息
  if (!userMessage && possibleCauses.length === 0 && solutions.length === 0) {
    userMessage = error;
  }

  return {
    userMessage: userMessage || "发生错误",
    possibleCauses,
    solutions,
    technicalDetails: technicalDetails || error,
  };
}

export const SmartErrorDisplay: React.FC<SmartErrorDisplayProps> = ({ error, style }) => {
  const [showTechnical, setShowTechnical] = useState(false);
  const parsed = parseErrorMessage(error);

  const hasStructuredError = parsed.possibleCauses.length > 0 || parsed.solutions.length > 0;

  if (!hasStructuredError) {
    // 如果没有结构化错误，显示简单的错误提示
    return (
      <Alert
        type="error"
        message="操作失败"
        description={error}
        showIcon
        style={style}
      />
    );
  }

  return (
    <div className={styles.smartErrorContainer} style={style}>
      <Alert
        type="error"
        message={parsed.userMessage}
        showIcon
        style={{ marginBottom: 16 }}
      />

      {parsed.possibleCauses.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <InfoCircleOutlined style={{ color: "#faad14", marginRight: 8 }} />
            <Text strong>可能原因</Text>
          </div>
          <ul className={styles.list}>
            {parsed.possibleCauses.map((cause, index) => (
              <li key={index}>{cause}</li>
            ))}
          </ul>
        </div>
      )}

      {parsed.solutions.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <BulbOutlined style={{ color: "#52c41a", marginRight: 8 }} />
            <Text strong>解决方案</Text>
          </div>
          <ol className={styles.orderedList}>
            {parsed.solutions.map((solution, index) => (
              <li key={index}>{solution}</li>
            ))}
          </ol>
        </div>
      )}

      <div className={styles.technicalSection}>
        <Button
          type="link"
          size="small"
          icon={<ToolOutlined />}
          onClick={() => setShowTechnical(!showTechnical)}
        >
          {showTechnical ? "隐藏" : "查看"}技术细节
        </Button>

        {showTechnical && (
          <div className={styles.technicalDetails}>
            <pre>{parsed.technicalDetails}</pre>
          </div>
        )}
      </div>
    </div>
  );
};
