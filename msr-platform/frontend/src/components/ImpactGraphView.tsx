import { useMemo } from "react";
import ReactFlow, { Background, Controls, MarkerType } from "reactflow";
import "reactflow/dist/style.css";
import type { Edge as GEdge } from "../types";
import { CI_CLASS_META } from "../ui";

interface NodeIn { id: string; name: string; ci_class: string; criticality?: string; is_root?: boolean; }

// Layout por capas (columnas) según ci_class
const LAYER_ORDER = ["business_service", "application", "database", "middleware", "runtime", "server"];

export default function ImpactGraphView({
  nodes, edges, height = 420,
}: { nodes: NodeIn[]; edges: GEdge[]; height?: number }) {
  const { rfNodes, rfEdges } = useMemo(() => {
    const byLayer: Record<string, NodeIn[]> = {};
    nodes.forEach((n) => { (byLayer[n.ci_class] ||= []).push(n); });
    const colX: Record<string, number> = {};
    LAYER_ORDER.forEach((l, i) => (colX[l] = i * 220));

    const rfNodes = nodes.map((n) => {
      const layerNodes = byLayer[n.ci_class];
      const idx = layerNodes.indexOf(n);
      const meta = CI_CLASS_META[n.ci_class] || { color: "#64748b", label: n.ci_class };
      return {
        id: n.id,
        position: { x: colX[n.ci_class] ?? 0, y: idx * 92 + (n.ci_class === "business_service" ? 40 : 0) },
        data: {
          label: (
            <div className="text-left">
              <div className="text-[10px] uppercase tracking-wide" style={{ color: meta.color }}>{meta.label}</div>
              <div className="text-xs font-semibold text-gray-100 leading-tight">{n.name}</div>
            </div>
          ),
        },
        style: {
          background: n.is_root ? "#3a1f1f" : "#1b1f27",
          border: `1.5px solid ${n.is_root ? "#ef4444" : meta.color}`,
          borderRadius: 10, padding: "6px 10px", width: 180, color: "#e5e7eb",
          boxShadow: n.is_root ? "0 0 0 3px rgba(239,68,68,0.25)" : "none",
        },
      };
    });

    const rfEdges = edges.map((e, i) => ({
      id: `e${i}`, source: e.source, target: e.target,
      label: e.type, animated: true,
      style: { stroke: "#3f4756" },
      labelStyle: { fill: "#64748b", fontSize: 9 },
      labelBgStyle: { fill: "#0b0d11" },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#3f4756" },
    }));
    return { rfNodes, rfEdges };
  }, [nodes, edges]);

  return (
    <div style={{ height }} className="rounded-lg overflow-hidden border border-line bg-ink">
      <ReactFlow nodes={rfNodes} edges={rfEdges} fitView minZoom={0.2} nodesDraggable={false} nodesConnectable={false}>
        <Background color="#1e232d" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
