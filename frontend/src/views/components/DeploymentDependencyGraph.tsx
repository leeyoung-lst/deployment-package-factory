import React, { useMemo } from "react";
import type { PackagePreview } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";

type PreviewDependencyItem = PackagePreview["middleware"][number];
type GraphKind = "business" | "platform" | "middleware" | "database";
type GraphNode = { id: string; key: string; label: string; kind: GraphKind; detail?: string; matchKeys: string[] };
type GraphEdge = { from: string; to: string; kind: "platform" | "middleware" };

export function DependencyGraph({ preview }: { preview: PackagePreview }) {
  const graph = useMemo(() => buildDependencyGraph(preview), [preview]);
  const layout = graphLayout(graph);
  return (
    <div className={`${styles.previewBlock} ${styles.dependencyGraphBlock}`}>
      <GraphHeader />
      <div className={styles.graphScroller}>
        <div className={styles.graphCanvas} style={{ width: layout.graphWidth, height: layout.graphHeight }}>
          <GraphRegions layout={layout} />
          <GraphEdges graph={graph} layout={layout} />
          {layout.nodes.map(({ node, position }) => <GraphNodeSlot key={node.id} node={node} position={position} />)}
          <GraphEmptySlots graph={graph} layout={layout} />
        </div>
      </div>
    </div>
  );
}

function GraphHeader() {
  return <div className={styles.graphHeader}><h3>依赖关系图</h3><div className={styles.graphLegend}><span><i className={styles.graphLegendBusiness} />业务</span><span><i className={styles.graphLegendPlatform} />平台</span><span><i className={styles.graphLegendMiddleware} />中间件</span><span><i className={styles.graphLegendDatabase} />数据库</span></div></div>;
}

function GraphRegions({ layout }: { layout: ReturnType<typeof graphLayout> }) {
  return (
    <>
      <div className={styles.graphRegion} style={{ left: 0, top: layout.topY, width: layout.sideBoxWidth, height: layout.sideBoxHeight }}><span>基础平台</span></div>
      <div className={styles.graphRegion} style={{ left: layout.rightBoxX, top: layout.topY, width: layout.sideBoxWidth, height: layout.sideBoxHeight }}><span>业务平台</span></div>
      <div className={`${styles.graphRegion} ${styles.graphRegionMiddleware}`} style={{ left: 0, top: layout.bottomBoxY, width: layout.graphWidth, height: layout.bottomBoxHeight }}><span>中间件 / 数据库</span></div>
    </>
  );
}

function GraphEdges({ graph, layout }: { graph: ReturnType<typeof buildDependencyGraph>; layout: ReturnType<typeof graphLayout> }) {
  if (!graph.edges.length) return null;
  return (
    <svg className={styles.graphEdges} viewBox={`0 0 ${layout.graphWidth} ${layout.graphHeight}`} preserveAspectRatio="none" aria-hidden="true">
      <defs><marker id="dependencyGraphArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker></defs>
      {graph.edges.map((edge) => <path key={`${edge.from}-${edge.to}`} className={edge.kind === "platform" ? styles.graphEdgePlatform : styles.graphEdgeMiddleware} d={edgePath(edge, layout.nodePositions)} markerEnd="url(#dependencyGraphArrow)" />)}
    </svg>
  );
}

function GraphNodeSlot({ node, position }: { node: GraphNode; position?: NodePosition }) {
  if (!position) return null;
  return <div className={styles.graphNodeSlot} style={{ left: position.x, top: position.y, width: position.width, height: position.height }}><GraphNodeView node={node} /></div>;
}

function GraphEmptySlots({ graph, layout }: { graph: ReturnType<typeof buildDependencyGraph>; layout: ReturnType<typeof graphLayout> }) {
  return <>{graph.platformNodes.length ? null : <div className={styles.graphEmptySlot} style={{ left: layout.framePadding, top: layout.sideNodeStartY, width: layout.sideNodeWidth, height: layout.nodeHeight }}>未选择</div>}{graph.businessNodes.length ? null : <div className={styles.graphEmptySlot} style={{ left: layout.rightBoxX + layout.sideBoxWidth - layout.framePadding - layout.sideNodeWidth, top: layout.sideNodeStartY, width: layout.sideNodeWidth, height: layout.nodeHeight }}>未选择</div>}{graph.middlewareNodes.length ? null : <div className={styles.graphEmptySlot} style={{ left: layout.bottomStartX, top: layout.bottomY, width: layout.bottomNodeWidth, height: layout.nodeHeight }}>未选择</div>}</>;
}

function GraphNodeView({ node }: { node: GraphNode }) {
  return <div className={`${styles.graphNode} ${graphNodeClassName(node.kind)}`} title={node.detail || node.label}><i className={graphNodeIcon(node.kind)} /><span className={styles.graphNodeText}><strong>{node.label}</strong><span>{node.detail || node.key}</span></span></div>;
}

type NodePosition = { x: number; y: number; width: number; height: number; lane: "platform" | "business" | "middleware" };

function graphLayout(graph: ReturnType<typeof buildDependencyGraph>) {
  const sideBoxWidth = 330, sideNodeWidth = 280, bottomNodeWidth = 228, nodeHeight = 48, sideGap = 12, bottomGap = 14, framePadding = 16, topY = 24, frameTitleHeight = 38;
  const sideRows = Math.max(1, graph.platformNodes.length, graph.businessNodes.length);
  const bottomNodeCount = Math.max(1, graph.middlewareNodes.length);
  const bottomWidth = bottomNodeCount * bottomNodeWidth + (bottomNodeCount - 1) * bottomGap;
  const graphWidth = Math.max(1080, bottomWidth + framePadding * 2, sideBoxWidth * 2 + 260);
  const rightBoxX = graphWidth - sideBoxWidth;
  const sideNodeStartY = topY + frameTitleHeight;
  const sideBoxHeight = Math.max(260, frameTitleHeight + sideRows * (nodeHeight + sideGap) - sideGap + framePadding);
  const bottomBoxY = topY + sideBoxHeight + 42;
  const bottomBoxHeight = Math.max(126, frameTitleHeight + nodeHeight + framePadding);
  const bottomY = bottomBoxY + frameTitleHeight;
  const bottomStartX = Math.max(framePadding, (graphWidth - bottomWidth) / 2);
  const graphHeight = bottomBoxY + bottomBoxHeight + 16;
  const nodePositions = new Map<string, NodePosition>();
  graph.platformNodes.forEach((node, index) => nodePositions.set(node.id, { x: framePadding, y: sideNodeStartY + index * (nodeHeight + sideGap), width: sideNodeWidth, height: nodeHeight, lane: "platform" }));
  graph.businessNodes.forEach((node, index) => nodePositions.set(node.id, { x: rightBoxX + sideBoxWidth - framePadding - sideNodeWidth, y: sideNodeStartY + index * (nodeHeight + sideGap), width: sideNodeWidth, height: nodeHeight, lane: "business" }));
  graph.middlewareNodes.forEach((node, index) => nodePositions.set(node.id, { x: bottomStartX + index * (bottomNodeWidth + bottomGap), y: bottomY, width: bottomNodeWidth, height: nodeHeight, lane: "middleware" }));
  const nodes = [...graph.platformNodes, ...graph.businessNodes, ...graph.middlewareNodes].map((node) => ({ node, position: nodePositions.get(node.id) }));
  return { bottomBoxHeight, bottomBoxY, bottomNodeWidth, bottomStartX, bottomY, framePadding, graphHeight, graphWidth, nodeHeight, nodePositions, nodes, rightBoxX, sideBoxHeight, sideBoxWidth, sideNodeStartY, sideNodeWidth, topY };
}

function edgePath(edge: GraphEdge, positions: Map<string, NodePosition>) {
  const from = positions.get(edge.from), to = positions.get(edge.to);
  if (!from || !to) return "";
  const fromCenterX = from.x + from.width / 2, fromCenterY = from.y + from.height / 2, toCenterX = to.x + to.width / 2, toCenterY = to.y + to.height / 2;
  if (from.lane === to.lane) { const outsideX = from.lane === "business" ? from.x - 26 : from.x + from.width + 26; const startX = from.lane === "business" ? from.x : from.x + from.width; return `M ${startX} ${fromCenterY} C ${outsideX} ${fromCenterY}, ${outsideX} ${toCenterY}, ${startX} ${toCenterY}`; }
  if (to.lane === "middleware") return `M ${fromCenterX} ${from.y + from.height} C ${fromCenterX} ${from.y + from.height + 42}, ${toCenterX} ${to.y - 42}, ${toCenterX} ${to.y}`;
  const fromX = from.x < to.x ? from.x + from.width : from.x, toX = from.x < to.x ? to.x : to.x + to.width, direction = fromX < toX ? 1 : -1, curve = Math.max(80, Math.abs(toX - fromX) / 2);
  return `M ${fromX} ${fromCenterY} C ${fromX + direction * curve} ${fromCenterY}, ${toX - direction * curve} ${toCenterY}, ${toX} ${toCenterY}`;
}

function buildDependencyGraph(preview: PackagePreview) {
  const businessNodes = runtimeGraphNodes(preview, "business", "business", preview.businessServices);
  const platformNodes = runtimeGraphNodes(preview, "platform", "platform", preview.platformServices);
  const middlewareNodes = runtimeGraphNodes(preview, "middleware", "middleware", preview.middleware);
  const sourceIds = new Map<string, string[]>(), platformIds = new Map<string, string>(), middlewareIds = new Map<string, string[]>();
  const addSourceNode = (node: GraphNode) => node.matchKeys.forEach((key) => sourceIds.set(key, [...(sourceIds.get(key) ?? []), node.id]));
  businessNodes.forEach(addSourceNode); platformNodes.forEach((node) => { addSourceNode(node); node.matchKeys.forEach((key) => platformIds.set(key, node.id)); });
  middlewareNodes.forEach((node) => node.matchKeys.forEach((key) => middlewareIds.set(key, [...(middlewareIds.get(key) ?? []), node.id])));
  const edges: GraphEdge[] = [], edgeKeys = new Set<string>();
  const addEdge = (from: string, to: string, kind: GraphEdge["kind"]) => { const key = `${from}->${to}`; if (from !== to && !edgeKeys.has(key)) { edgeKeys.add(key); edges.push({ from, to, kind }); } };
  preview.platformServices.forEach((item) => item.requiredBy.forEach((requiredBy) => (sourceIds.get(requiredBy) ?? []).forEach((sourceId) => platformIds.get(item.key) && addEdge(sourceId, platformIds.get(item.key)!, "platform"))));
  preview.middleware.forEach((item) => item.requiredBy.forEach((requiredBy) => (sourceIds.get(requiredBy) ?? []).forEach((sourceId) => (middlewareIds.get(item.key) ?? []).forEach((targetId) => addEdge(sourceId, targetId, "middleware")))));
  return { businessNodes, platformNodes, middlewareNodes, edges };
}

function runtimeGraphNodes(preview: PackagePreview, group: "business" | "platform" | "middleware", kind: GraphKind, fallbackItems: PreviewDependencyItem[]): GraphNode[] {
  const nodes = (preview.imageEntries ?? []).filter((item) => item.group === group).map((item) => runtimeGraphNode(preview, item, kind)).filter((item): item is GraphNode => Boolean(item));
  const keys = new Set(nodes.flatMap((node) => node.matchKeys));
  fallbackItems.forEach((item) => { if (!keys.has(item.key)) nodes.push(toGraphNode(item.key === preview.database.key ? "database" : kind, item)); });
  if (group === "middleware" && !nodes.some((node) => node.key === preview.database.key)) nodes.push({ id: `database:${preview.database.key}`, key: preview.database.key, label: preview.database.name, kind: "database", detail: preview.database.image, matchKeys: [preview.database.key] });
  return nodes;
}

function toGraphNode(kind: GraphKind, item: PreviewDependencyItem): GraphNode {
  return { id: `${kind}:${item.key}`, key: item.key, label: item.name, kind, detail: item.namespace || item.reason || item.key, matchKeys: [item.key] };
}

function runtimeGraphNode(preview: PackagePreview, item: PackagePreview["imageEntries"][number], kind: GraphKind): GraphNode | null {
  const sourceRef = item.sourceRef || item.catalogRef || item.targetRef, label = item.sourceContainer || item.sourcePod || imageName(sourceRef);
  if (!sourceRef || !label) return null;
  return { id: `${item.group}:${item.sourceNamespace || "runtime"}:${item.sourcePod || imageName(sourceRef)}:${item.sourceContainer || imageName(sourceRef)}`, key: sourceRef, label, kind: kind === "middleware" && matchesRuntimeDependency(preview.database.key, preview.database.name, item) ? "database" : kind, detail: runtimeNodeDetail(item, sourceRef), matchKeys: runtimeMatchKeys(preview, item, kind) };
}

function runtimeMatchKeys(preview: PackagePreview, item: PackagePreview["imageEntries"][number], kind: GraphKind): string[] {
  if (kind === "business") return dependencyMatches(preview.businessServices, item).length ? dependencyMatches(preview.businessServices, item) : preview.businessServices.map((entry) => entry.key);
  if (kind === "platform") return dependencyMatches(preview.platformServices, item);
  const middlewareMatches = dependencyMatches(preview.middleware, item);
  if (middlewareMatches.length) return middlewareMatches;
  return matchesRuntimeDependency(preview.database.key, preview.database.name, item) ? [preview.database.key] : [];
}

function dependencyMatches(items: PreviewDependencyItem[], image: PackagePreview["imageEntries"][number]) {
  return items.filter((item) => matchesRuntimeDependency(item.key, item.name, image)).map((item) => item.key);
}

function matchesRuntimeDependency(key: string, name: string, image: PackagePreview["imageEntries"][number]) {
  const haystack = normalizeGraphText([image.catalogRef, image.sourceRef, image.targetRef, image.sourceNamespace, image.sourcePod, image.sourceContainer].filter(Boolean).join(" "));
  return normalizeGraphText(key) && haystack.includes(normalizeGraphText(key)) || normalizeGraphText(name) && haystack.includes(normalizeGraphText(name)) || key.split("-").some((part) => part.length >= 4 && haystack.includes(normalizeGraphText(part)));
}

function runtimeNodeDetail(item: PackagePreview["imageEntries"][number], sourceRef: string) {
  return `${item.sourceNamespace ? `${item.sourceNamespace}/` : ""}${item.sourceContainer ? `${item.sourceContainer} · ` : ""}${sourceRef}`;
}

function imageName(image: string) {
  return (image.split("@", 1)[0].split("/").pop() || image).split(":", 1)[0] || image;
}

function normalizeGraphText(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function graphNodeClassName(kind: GraphKind) {
  if (kind === "business") return styles.graphNodeBusiness;
  if (kind === "platform") return styles.graphNodePlatform;
  if (kind === "database") return styles.graphNodeDatabase;
  return styles.graphNodeMiddleware;
}

function graphNodeIcon(kind: GraphKind) {
  if (kind === "business") return "ri-building-4-line";
  if (kind === "platform") return "ri-apps-2-line";
  if (kind === "database") return "ri-database-2-line";
  return "ri-server-line";
}
