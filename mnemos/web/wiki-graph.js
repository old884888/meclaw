/**
 * Wiki graph with project-centric clustered layout.
 * - note = project hub (big circle)
 * - concept = child node (small circle)
 * - can collapse/expand concept nodes
 */
class WikiGraphView {
  constructor(container, options = {}) {
    this.container = container;
    this.onNodeSelect = options.onNodeSelect || null;
    this.rawNodes = [];
    this.rawEdges = [];
    this.visibleNodes = [];
    this.visibleEdges = [];
    this.noteNodes = [];
    this.conceptNodes = [];
    this.conceptExpanded = options.conceptExpanded ?? false;
    this.positions = new Map();
    this.selectedId = null;
    this.scale = 1;
    this.panX = 0;
    this.panY = 0;
    this.draggingNode = null;
    this.panning = false;
    this.lastPointer = { x: 0, y: 0 };
    this._buildDom();
    this._bindEvents();
  }

  _buildDom() {
    this.container.innerHTML = "";
    this.container.classList.add("wiki-graph-stage");

    this.emptyEl = document.createElement("div");
    this.emptyEl.className = "wiki-graph-empty hidden";
    this.emptyEl.textContent = "暂无关系节点。导入知识卡片后点击「重建 Wiki」。";
    this.container.appendChild(this.emptyEl);

    this.svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    this.svg.setAttribute("class", "wiki-graph-svg");
    this.viewport = document.createElementNS("http://www.w3.org/2000/svg", "g");
    this.viewport.setAttribute("class", "wiki-graph-viewport");
    this.edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    this.edgeLayer.setAttribute("class", "wiki-graph-edges");
    this.nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    this.nodeLayer.setAttribute("class", "wiki-graph-nodes");
    this.viewport.appendChild(this.edgeLayer);
    this.viewport.appendChild(this.nodeLayer);
    this.svg.appendChild(this.viewport);
    this.container.appendChild(this.svg);
  }

  _bindEvents() {
    this.svg.addEventListener("wheel", (e) => this._onWheel(e), { passive: false });
    this.svg.addEventListener("pointerdown", (e) => this._onPointerDown(e));
    window.addEventListener("pointermove", (e) => this._onPointerMove(e));
    window.addEventListener("pointerup", () => this._onPointerUp());
    window.addEventListener("pointercancel", () => this._onPointerUp());
    if (typeof ResizeObserver !== "undefined") {
      this._resizeObserver = new ResizeObserver(() => this._syncSize());
      this._resizeObserver.observe(this.container);
    } else {
      window.addEventListener("resize", () => this._syncSize());
    }
  }

  destroy() {
    if (this._resizeObserver) this._resizeObserver.disconnect();
  }

  setData(graph) {
    this.rawNodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
    this.rawEdges = Array.isArray(graph?.edges) ? graph.edges : [];
    this._buildGraphIndex();
    this._applyVisibility(true);
  }

  isConceptExpanded() {
    return !!this.conceptExpanded;
  }

  setConceptExpanded(expanded) {
    this.conceptExpanded = !!expanded;
    this._applyVisibility();
  }

  toggleConceptExpanded() {
    this.setConceptExpanded(!this.conceptExpanded);
  }

  getStats() {
    const visibleConcepts = this.visibleNodes.filter((n) => n.kind !== "note").length;
    const visibleNotes = this.visibleNodes.filter((n) => n.kind === "note").length;
    return {
      totalNodes: this.rawNodes.length,
      totalEdges: this.rawEdges.length,
      visibleNodes: this.visibleNodes.length,
      visibleEdges: this.visibleEdges.length,
      visibleNotes,
      visibleConcepts,
      conceptExpanded: this.conceptExpanded,
    };
  }

  _buildGraphIndex() {
    this.noteNodes = this.rawNodes.filter((n) => n.kind === "note");
    this.conceptNodes = this.rawNodes.filter((n) => n.kind !== "note");
    this.nodeById = new Map(this.rawNodes.map((n) => [n.id, n]));
    this.conceptParents = new Map();
    for (const edge of this.rawEdges) {
      const from = this.nodeById.get(edge.from);
      const to = this.nodeById.get(edge.to);
      if (!from || !to) continue;
      if (from.kind === "note" && to.kind !== "note") {
        if (!this.conceptParents.has(to.id)) this.conceptParents.set(to.id, []);
        this.conceptParents.get(to.id).push(from.id);
      }
    }
  }

  _applyVisibility(resetView = false) {
    if (!this.rawNodes.length) {
      this.emptyEl.classList.remove("hidden");
      this.svg.classList.add("hidden");
      this.visibleNodes = [];
      this.visibleEdges = [];
      return;
    }

    const noteIds = new Set(this.noteNodes.map((n) => n.id));
    if (!this.conceptExpanded) {
      this.visibleNodes = [...this.noteNodes];
      this.visibleEdges = [];
    } else {
      this.visibleNodes = [...this.rawNodes];
      this.visibleEdges = this.rawEdges.filter((e) => noteIds.has(e.from));
    }

    if (this.selectedId && !this.visibleNodes.some((n) => n.id === this.selectedId)) {
      this.selectedId = null;
    }

    this.emptyEl.classList.add("hidden");
    this.svg.classList.remove("hidden");
    this._syncSize();
    this._runLayout();
    this._renderGraph();
    if (resetView) this.fitView();
    else this._applyTransform();
  }

  focusNode(id) {
    const pos = this.positions.get(id);
    if (!pos) return;
    this.selectNode(id);
    const rect = this.container.getBoundingClientRect();
    this.panX = rect.width / 2 - pos.x * this.scale;
    this.panY = rect.height / 2 - pos.y * this.scale;
    this._applyTransform();
  }

  resetView() {
    this.scale = 1;
    this.panX = 0;
    this.panY = 0;
    this._applyTransform();
  }

  fitView() {
    if (!this.positions.size) return;
    const rect = this.container.getBoundingClientRect();
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const pos of this.positions.values()) {
      minX = Math.min(minX, pos.x - 40);
      minY = Math.min(minY, pos.y - 40);
      maxX = Math.max(maxX, pos.x + 40);
      maxY = Math.max(maxY, pos.y + 40);
    }
    const bw = Math.max(maxX - minX, 80);
    const bh = Math.max(maxY - minY, 80);
    const pad = 48;
    const sx = (rect.width - pad * 2) / bw;
    const sy = (rect.height - pad * 2) / bh;
    this.scale = Math.max(0.35, Math.min(2.5, Math.min(sx, sy)));
    this.panX = pad - minX * this.scale + (rect.width - pad * 2 - bw * this.scale) / 2;
    this.panY = pad - minY * this.scale + (rect.height - pad * 2 - bh * this.scale) / 2;
    this._applyTransform();
  }

  selectNode(id) {
    this.selectedId = id || null;
    this._updateHighlight();
    if (this.onNodeSelect && id) {
      const node = this.nodes.find((n) => n.id === id);
      if (node) this.onNodeSelect(node);
    }
  }

  _syncSize() {
    const rect = this.container.getBoundingClientRect();
    const w = Math.max(rect.width, 320);
    const h = Math.max(rect.height, 360);
    this.svg.setAttribute("width", String(w));
    this.svg.setAttribute("height", String(h));
    this.svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    if (this.visibleNodes.length && this.positions.size === 0) {
      this._runLayout();
      this._renderGraph();
    }
  }

  _runLayout() {
    const pinned = new Map();
    for (const [id, pos] of this.positions.entries()) {
      if (pos?.pinned) pinned.set(id, pos);
    }

    const next = new Map();
    const clusters = this._buildClusters();
    const cols = Math.max(1, Math.ceil(Math.sqrt(clusters.length || 1)));
    const spacingX = 360;
    const spacingY = 300;
    const baseX = 140;
    const baseY = 110;

    clusters.forEach((cluster, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const cx = baseX + col * spacingX;
      const cy = baseY + row * spacingY;

      const center = pinned.get(cluster.note.id) || { x: cx, y: cy, pinned: false };
      next.set(cluster.note.id, { x: center.x, y: center.y, pinned: !!center.pinned });

      const children = cluster.concepts;
      const count = children.length;
      if (!count) return;
      const radius = 78 + Math.min(120, count * 8);
      const start = (25 * Math.PI) / 180;
      const end = (155 * Math.PI) / 180;
      children.forEach((child, i) => {
        const saved = pinned.get(child.id);
        if (saved) {
          next.set(child.id, { x: saved.x, y: saved.y, pinned: true });
          return;
        }
        const t = count === 1 ? 0.5 : i / (count - 1);
        const angle = start + (end - start) * t;
        next.set(child.id, {
          x: center.x + Math.cos(angle) * radius,
          y: center.y + Math.sin(angle) * radius + 28,
          pinned: false,
        });
      });
    });

    this.positions = next;
  }

  _buildClusters() {
    const notes = this.noteNodes.filter((n) => this.visibleNodes.some((x) => x.id === n.id));
    const concepts = this.conceptNodes.filter((n) => this.visibleNodes.some((x) => x.id === n.id));
    const owner = new Map();
    for (const concept of concepts) {
      const parents = this.conceptParents.get(concept.id) || [];
      owner.set(concept.id, parents[0] || null);
    }
    const conceptsByNote = new Map(notes.map((n) => [n.id, []]));
    for (const concept of concepts) {
      const parentId = owner.get(concept.id);
      if (parentId && conceptsByNote.has(parentId)) {
        conceptsByNote.get(parentId).push(concept);
      }
    }
    const clusters = notes.map((note) => ({
      note,
      concepts: (conceptsByNote.get(note.id) || []).sort((a, b) =>
        String(a.title || a.id).localeCompare(String(b.title || b.id), "zh-CN")
      ),
    }));
    return clusters.sort((a, b) =>
      String(a.note.title || a.note.id).localeCompare(String(b.note.title || b.note.id), "zh-CN")
    );
  }

  _renderGraph() {
    this.edgeLayer.innerHTML = "";
    this.nodeLayer.innerHTML = "";
    this._edgeEls = new Map();
    this._nodeEls = new Map();

    for (const edge of this.visibleEdges) {
      const from = this.positions.get(edge.from);
      const to = this.positions.get(edge.to);
      if (!from || !to) continue;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", String(from.x));
      line.setAttribute("y1", String(from.y));
      line.setAttribute("x2", String(to.x));
      line.setAttribute("y2", String(to.y));
      line.setAttribute("class", "wiki-graph-edge");
      line.dataset.from = edge.from;
      line.dataset.to = edge.to;
      this.edgeLayer.appendChild(line);
      this._edgeEls.set(`${edge.from}->${edge.to}`, line);
    }

    for (const node of this.visibleNodes) {
      const pos = this.positions.get(node.id);
      if (!pos) continue;
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", "wiki-graph-node");
      group.dataset.id = node.id;
      group.setAttribute("transform", `translate(${pos.x}, ${pos.y})`);

      const radius = node.kind === "concept" ? 14 : 26;
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("r", String(radius));
      circle.setAttribute("class", `wiki-graph-node-circle kind-${node.kind || "note"}`);
      group.appendChild(circle);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("class", `wiki-graph-node-label kind-${node.kind || "note"}`);
      label.setAttribute("y", String(radius + 16));
      label.textContent = this._truncate(node.title || node.id, node.kind === "concept" ? 12 : 18);
      group.appendChild(label);

      group.addEventListener("pointerdown", (e) => this._onNodePointerDown(e, node.id));
      group.addEventListener("click", (e) => {
        e.stopPropagation();
        this.selectNode(node.id);
      });
      this.nodeLayer.appendChild(group);
      this._nodeEls.set(node.id, group);
    }
  }

  _truncate(text, max) {
    const value = String(text || "");
    return value.length > max ? `${value.slice(0, max - 1)}…` : value;
  }

  _connectedIds(id) {
    const ids = new Set([id]);
    for (const edge of this.visibleEdges) {
      if (edge.from === id) ids.add(edge.to);
      if (edge.to === id) ids.add(edge.from);
    }
    return ids;
  }

  _updateHighlight() {
    const active = this.selectedId ? this._connectedIds(this.selectedId) : null;
    for (const [id, el] of this._nodeEls.entries()) {
      const dim = active && !active.has(id);
      el.classList.toggle("dimmed", dim);
      el.classList.toggle("selected", id === this.selectedId);
    }
    for (const [key, el] of this._edgeEls.entries()) {
      const [from, to] = key.split("->");
      const hit =
        this.selectedId &&
        (from === this.selectedId || to === this.selectedId);
      el.classList.toggle("highlight", !!hit);
      el.classList.toggle("dimmed", !!this.selectedId && !hit);
    }
  }

  _applyTransform() {
    this.viewport.setAttribute(
      "transform",
      `translate(${this.panX}, ${this.panY}) scale(${this.scale})`
    );
  }

  _clientToGraph(clientX, clientY) {
    const rect = this.svg.getBoundingClientRect();
    const x = (clientX - rect.left - this.panX) / this.scale;
    const y = (clientY - rect.top - this.panY) / this.scale;
    return { x, y };
  }

  _onWheel(e) {
    e.preventDefault();
    const rect = this.svg.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.08 : 0.92;
    const next = Math.max(0.35, Math.min(2.8, this.scale * factor));
    this.panX = mx - ((mx - this.panX) * next) / this.scale;
    this.panY = my - ((my - this.panY) * next) / this.scale;
    this.scale = next;
    this._applyTransform();
  }

  _onPointerDown(e) {
    if (e.target.closest(".wiki-graph-node")) return;
    this.panning = true;
    this.lastPointer = { x: e.clientX, y: e.clientY };
    this.svg.setPointerCapture?.(e.pointerId);
  }

  _onNodePointerDown(e, id) {
    e.stopPropagation();
    this.draggingNode = id;
    this.selectNode(id);
    this.lastPointer = { x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }

  _onPointerMove(e) {
    if (this.draggingNode) {
      const pos = this.positions.get(this.draggingNode);
      if (!pos) return;
      const dx = (e.clientX - this.lastPointer.x) / this.scale;
      const dy = (e.clientY - this.lastPointer.y) / this.scale;
      pos.x += dx;
      pos.y += dy;
      pos.pinned = true;
      const group = this._nodeEls.get(this.draggingNode);
      if (group) group.setAttribute("transform", `translate(${pos.x}, ${pos.y})`);
      this._refreshEdgesForNode(this.draggingNode);
      this.lastPointer = { x: e.clientX, y: e.clientY };
      return;
    }
    if (this.panning) {
      const dx = e.clientX - this.lastPointer.x;
      const dy = e.clientY - this.lastPointer.y;
      this.panX += dx;
      this.panY += dy;
      this.lastPointer = { x: e.clientX, y: e.clientY };
      this._applyTransform();
    }
  }

  _refreshEdgesForNode(id) {
    for (const edge of this.visibleEdges) {
      if (edge.from !== id && edge.to !== id) continue;
      const line = this._edgeEls.get(`${edge.from}->${edge.to}`);
      const from = this.positions.get(edge.from);
      const to = this.positions.get(edge.to);
      if (!line || !from || !to) continue;
      line.setAttribute("x1", String(from.x));
      line.setAttribute("y1", String(from.y));
      line.setAttribute("x2", String(to.x));
      line.setAttribute("y2", String(to.y));
    }
  }

  _onPointerUp() {
    this.draggingNode = null;
    this.panning = false;
  }
}
