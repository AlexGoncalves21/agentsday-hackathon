import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Minus,
  Plus,
  RotateCcw,
  Search,
} from 'lucide-react'
import './styles.css'

const LAST_SEEN_GRAPH_KEY = 'agentsday:lastSeenGraphState'
const EXCLUDED_NODE_IDS = new Set(['README.md', 'changelog.md', 'index.md', 'open_questions.md', 'schema.md'])
const EXCLUDED_NODE_PREFIXES = ['sources/']

const CATEGORY_COLORS = {
  company: '#009e73',
  concept: '#31576b',
  core: '#164455',
  event: '#4d85a3',
  person: '#0072b2',
  project: '#0b8f74',
  source: '#8fa7b2',
  topic: '#00a6a6',
  work: '#245d68',
}

const NODE_RADIUS = 7.25
const NODE_HIT_RADIUS = 20.25
const NODE_LABEL_FONT_SIZE = 11.5
const NODE_LABEL_STROKE_WIDTH = 3

function displayStatus(status, isSeen) {
  return isSeen ? 'unchanged' : status
}

function nodeColor(node, isSeen) {
  return CATEGORY_COLORS[node.type] || CATEGORY_COLORS.core
}

function linkColor(link, isSeen) {
  const status = displayStatus(link.status, isSeen)
  return status === 'new' ? '#24997f' : 'rgba(49, 87, 107, 0.46)'
}

function labelPlacementsFor(nodes, unitsPerPixel, visibleIds) {
  const occupiedRects = nodes.map((node) => {
    const radius = (NODE_RADIUS + 7) * unitsPerPixel
    return {
      left: node.x - radius,
      right: node.x + radius,
      top: node.y - radius,
      bottom: node.y + radius,
    }
  })
  const placements = new Map()
  const labelNodes = nodes.filter((node) => visibleIds.has(node.id)).sort((left, right) => left.id.localeCompare(right.id))

  for (const node of labelNodes) {
    const placement = labelPlacementFor(node, unitsPerPixel, occupiedRects)
    placements.set(node.id, placement)
    occupiedRects.push(placement.rect)
  }

  return placements
}

function labelPlacementFor(node, unitsPerPixel, occupiedRects) {
  const labelWidth = Math.min(220, Math.max(54, node.label.length * 6.4)) * unitsPerPixel
  const labelHeight = 16 * unitsPerPixel
  const baseGap = (NODE_RADIUS + 16) * unitsPerPixel
  const verticalOffset = 4 * unitsPerPixel
  const candidates = [
    { x: baseGap, y: verticalOffset, anchor: 'start' },
    { x: -baseGap, y: verticalOffset, anchor: 'end' },
    { x: 0, y: -baseGap, anchor: 'middle' },
    { x: 0, y: baseGap + 10 * unitsPerPixel, anchor: 'middle' },
    { x: baseGap, y: -baseGap, anchor: 'start' },
    { x: -baseGap, y: -baseGap, anchor: 'end' },
    { x: baseGap, y: baseGap + 10 * unitsPerPixel, anchor: 'start' },
    { x: -baseGap, y: baseGap + 10 * unitsPerPixel, anchor: 'end' },
    { x: baseGap * 1.85, y: verticalOffset, anchor: 'start' },
    { x: -baseGap * 1.85, y: verticalOffset, anchor: 'end' },
    { x: 0, y: -baseGap * 1.85, anchor: 'middle' },
    { x: 0, y: baseGap * 1.85 + 10 * unitsPerPixel, anchor: 'middle' },
  ]

  const placements = candidates.map((candidate) => {
    const rect = labelRectFor(node, candidate, labelWidth, labelHeight, unitsPerPixel)
    return { ...candidate, rect, overlap: occupiedRects.filter((occupiedRect) => rectsOverlap(rect, occupiedRect)).length }
  })

  return placements.find((placement) => placement.overlap === 0) || placements.sort((left, right) => left.overlap - right.overlap)[0]
}

function labelRectFor(node, candidate, width, height, unitsPerPixel) {
  const absoluteX = node.x + candidate.x
  const absoluteY = node.y + candidate.y
  const left =
    candidate.anchor === 'end' ? absoluteX - width : candidate.anchor === 'middle' ? absoluteX - width / 2 : absoluteX
  return {
    left,
    right: left + width,
    top: absoluteY - height + 3 * unitsPerPixel,
    bottom: absoluteY + 5 * unitsPerPixel,
  }
}

function rectsOverlap(left, right) {
  return left.left < right.right && left.right > right.left && left.top < right.bottom && left.bottom > right.top
}

export default function App() {
  const paneRef = useRef(null)
  const svgRef = useRef(null)
  const dragRef = useRef(null)
  const panRef = useRef(null)
  const scanMessageTimerRef = useRef(null)
  const [graph, setGraph] = useState(null)
  const [graphHistory, setGraphHistory] = useState([])
  const [currentGraphIndex, setCurrentGraphIndex] = useState(0)
  const [evolutionMode, setEvolutionMode] = useState(false)
  const [selected, setSelected] = useState(null)
  const [selectedLink, setSelectedLink] = useState(null)
  const [selectedMarkdown, setSelectedMarkdown] = useState('')
  const [selectedMarkdownError, setSelectedMarkdownError] = useState(null)
  const [readerExpanded, setReaderExpanded] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 })
  const [hoveredId, setHoveredId] = useState(null)
  const [draggingId, setDraggingId] = useState(null)
  const [isPanning, setIsPanning] = useState(false)
  const [displayNodes, setDisplayNodes] = useState([])
  const [error, setError] = useState(null)
  const [graphLoadComplete, setGraphLoadComplete] = useState(false)
  const [scanState, setScanState] = useState({ running: false, message: '', tone: 'neutral' })
  const [previousGraphState, setPreviousGraphState] = useState(() => loadStoredGraphState())

  async function loadGraph(options = {}) {
    const { simulateEvolution = true } = options
    try {
      setError(null)
      const [graphResponse, historyResponse] = await Promise.all([
        fetch('/brain/graph.json', { cache: 'no-store' }),
        fetch('/brain/graph_history.json', { cache: 'no-store' }),
      ])
      if (graphResponse.status === 404) {
        setGraph(null)
        setGraphHistory([])
        setCurrentGraphIndex(0)
        setEvolutionMode(false)
        setGraphLoadComplete(true)
        return null
      }
      if (!graphResponse.ok) throw new Error('Unable to load brain/graph.json.')
      const nextGraph = sanitizeGraph(await graphResponse.json())
      const historyPayload = historyResponse.ok ? await historyResponse.json() : null
      const historyGraphs = normalizeHistory(historyPayload, nextGraph, { simulateEvolution })
      const nextIndex = historyGraphs.findIndex((historyGraph) => historyGraph.build_id === nextGraph.build_id)
      setGraphHistory(historyGraphs)
      setCurrentGraphIndex(nextIndex >= 0 ? nextIndex : historyGraphs.length - 1)
      setGraph(historyGraphs[nextIndex >= 0 ? nextIndex : historyGraphs.length - 1] || nextGraph)
      localStorage.setItem(LAST_SEEN_GRAPH_KEY, JSON.stringify(snapshotGraphState(nextGraph)))
      setGraphLoadComplete(true)
      return { historyGraphs, graphIndex: nextIndex >= 0 ? nextIndex : historyGraphs.length - 1, graph: nextGraph }
    } catch (loadError) {
      setError(loadError.message)
      setGraphLoadComplete(true)
      return null
    }
  }

  useEffect(() => {
    loadGraph()
    return () => {
      if (scanMessageTimerRef.current) window.clearTimeout(scanMessageTimerRef.current)
    }
  }, [])

  useEffect(() => {
    if (!graphHistory.length) return
    setGraph(graphHistory[currentGraphIndex])
    setSelected(null)
    setSelectedLink(null)
  }, [currentGraphIndex, graphHistory])

  useEffect(() => {
    async function loadSelectedMarkdown() {
      if (!selected?.path) {
        setSelectedMarkdown('')
        setSelectedMarkdownError(null)
        return
      }

      try {
        setSelectedMarkdownError(null)
        const response = await fetch(`/${selected.path}`, { cache: 'no-store' })
        if (!response.ok) throw new Error('Unable to load Markdown text.')
        setSelectedMarkdown(await response.text())
      } catch (markdownError) {
        setSelectedMarkdown('')
        setSelectedMarkdownError(markdownError.message)
      }
    }

    loadSelectedMarkdown()
  }, [selected])

  const isSeen = graph?.build_id && graph.build_id === previousGraphState?.build_id
  const statusIsSeen = evolutionMode ? false : isSeen

  const nodes = useMemo(() => {
    if (!graph) return []
    const laidOutNodes = stableLayout(graph.nodes, graph.edges).map((node) => ({ ...node, size: NODE_RADIUS }))
    return laidOutNodes.map((node, index) => {
      const status = evolutionMode ? node.status : statusForNode(node, previousGraphState)
      return {
        ...node,
        index,
        status,
        color: nodeColor({ ...node, status }, statusIsSeen),
      }
    })
  }, [evolutionMode, graph, previousGraphState, statusIsSeen])

  useEffect(() => {
    setDisplayNodes(nodes)
  }, [nodes])

  useEffect(() => {
    setPanOffset({ x: 0, y: 0 })
  }, [graph?.build_id])

  const renderedNodes = displayNodes.length ? displayNodes : nodes

  const nodeIndexesById = useMemo(() => {
    return Object.fromEntries(renderedNodes.map((node, index) => [node.id, index]))
  }, [renderedNodes])

  const nodesById = useMemo(() => {
    return Object.fromEntries(renderedNodes.map((node) => [node.id, node]))
  }, [renderedNodes])

  const adjacency = useMemo(() => {
    return graph ? adjacencyFor(graph.nodes, graph.edges) : new Map()
  }, [graph])

  const links = useMemo(() => {
    if (!graph) return []
    return graph.edges.map((edge) => {
      const status = evolutionMode ? edge.status : statusForEdge(edge, previousGraphState)
      return {
        ...edge,
        status,
        sourceIndex: nodeIndexesById[edge.source],
        targetIndex: nodeIndexesById[edge.target],
        color: linkColor({ ...edge, status }, statusIsSeen),
        width: status === 'new' && !statusIsSeen ? (evolutionMode ? 3.8 : 2.15) : 1.35,
      }
    })
  }, [evolutionMode, graph, nodeIndexesById, previousGraphState, statusIsSeen])

  function beginDrag(event, node, point) {
    event.preventDefault()
    dragRef.current = { id: node.id, clientX: event.clientX, clientY: event.clientY, x: point.x, y: point.y }
    panRef.current = null
    setIsPanning(false)
    setDraggingId(node.id)
    setHoveredId(node.id)
    setSelectedLink(null)
    setSelected(node)
  }

  function handleGraphMouseMove(event) {
    const drag = dragRef.current
    if (drag) {
      const scale = graphScaleFor(paneRef.current, graphViewBox)
      if (!scale) return
      const dx = (event.clientX - drag.clientX) / scale
      const dy = (event.clientY - drag.clientY) / scale
      if (!dx && !dy) return
      dragRef.current = { ...drag, clientX: event.clientX, clientY: event.clientY }
      setDisplayNodes((currentNodes) => pullConnectedNodes(currentNodes, drag.id, dx, dy, adjacency))
      return
    }

    const pan = panRef.current
    if (pan) {
      const scale = graphScaleFor(paneRef.current, graphViewBox)
      if (!scale) return
      const dx = (event.clientX - pan.clientX) / scale
      const dy = (event.clientY - pan.clientY) / scale
      panRef.current = { ...pan, clientX: event.clientX, clientY: event.clientY }
      setDisplayNodes((currentNodes) => moveAllNodes(currentNodes, dx, dy))
      return
    }

    if (!isInsidePane(event, paneRef.current)) {
      setHoveredId(null)
      return
    }

    const point = graphPointFor(event, paneRef.current, graphViewBox)
    if (!point) return

    const hoverNode = nearestNodeAtPoint(point, renderedNodes, paneRef.current, graphViewBox)
    setHoveredId(hoverNode?.id || null)
    if (hoverNode) {
      setSelectedLink(null)
      setSelected(hoverNode)
      return
    }

  }

  function endGraphInteraction() {
    dragRef.current = null
    setDraggingId(null)
    panRef.current = null
    setIsPanning(false)
  }

  function handleGraphMouseDown(event) {
    if (event.target.closest?.('.zoom-controls')) return
    if (event.button !== 0) return
    if (!isInsidePane(event, paneRef.current)) return

    const point = graphPointFor(event, paneRef.current, graphViewBox)
    if (!point) return
    const node = nearestNodeAtPoint(point, renderedNodes, paneRef.current, graphViewBox)
    if (node) {
      beginDrag(event, node, point)
      return
    }

    const link = nearestLinkAtPoint(point, links, renderedNodes, paneRef.current, graphViewBox)
    if (link) {
      event.preventDefault()
      setSelectedLink(link)
      setSelected(null)
      return
    }

    event.preventDefault()
    panRef.current = { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY }
    setIsPanning(true)
  }

  function handleGraphMouseLeave() {
    setHoveredId(null)
  }

  function toggleEvolutionMode() {
    const nextEnabled = !evolutionMode
    setEvolutionMode(nextEnabled)
    setCurrentGraphIndex(Math.max(graphHistory.length - 1, 0))
  }

  function setScanStatus(nextState, clearAfterMs) {
    if (scanMessageTimerRef.current) window.clearTimeout(scanMessageTimerRef.current)
    setScanState(nextState)
    if (clearAfterMs) {
      scanMessageTimerRef.current = window.setTimeout(() => {
        setScanState((currentState) => ({ ...currentState, message: '', tone: 'neutral' }))
        scanMessageTimerRef.current = null
      }, clearAfterMs)
    }
  }

  async function scanInput() {
    if (scanState.running) return
    setScanStatus({ running: true, message: 'Scanning input...', tone: 'neutral' })
    const graphBeforeScan = graph
    try {
      const pendingResponse = await fetch('/api/scan-input', { cache: 'no-store' })
      const pendingResult = await pendingResponse.json()
      const hasPendingInputs = pendingResult.pendingInputs?.length > 0
      if (!hasPendingInputs) {
        setScanStatus({ running: false, message: 'No new input Markdown files found.', tone: 'neutral' }, 5000)
        return
      }
      if (hasPendingInputs) {
        setScanStatus({ running: true, message: 'Processing new files...', tone: 'info' })
      }

      const response = await fetch('/api/scan-input', { method: 'POST' })
      const result = await response.json()
      if (!response.ok) {
        setScanStatus({
          running: false,
          message: hasPendingInputs ? 'Processing failed. Check the input file format.' : result.message || 'Scan failed.',
          tone: 'neutral',
        })
        return
      }
      const loaded = await loadGraph({ simulateEvolution: false })
      if (result.processed && loaded) {
        const scanHistory = graphBeforeScan
          ? scanEvolutionHistoryFor(graphBeforeScan, loaded.graph, result.processedNodeIds || [])
          : loaded.historyGraphs
        setGraphHistory(scanHistory)
        setGraph(scanHistory[scanHistory.length - 1])
        setEvolutionMode(Boolean(graphBeforeScan) && scanHistory.length > 1)
        setCurrentGraphIndex(scanHistory.length - 1)
      }
      setScanStatus({ running: false, message: result.message, tone: result.processed ? 'info' : 'neutral' })
    } catch (scanError) {
      setScanStatus({ running: false, message: scanError.message, tone: 'neutral' })
    }
  }

  async function resetNetwork() {
    if (scanState.running) return
    setScanStatus({ running: true, message: 'Resetting network...', tone: 'neutral' })
    try {
      const response = await fetch('/api/reset-network', { method: 'POST' })
      const result = await response.json()
      if (!response.ok) throw new Error(result.message || 'Reset failed.')
      setGraph(null)
      setGraphHistory([])
      setGraphLoadComplete(true)
      setCurrentGraphIndex(0)
      setEvolutionMode(false)
      setSelected(null)
      setSelectedLink(null)
      setSelectedMarkdown('')
      setSelectedMarkdownError(null)
      setReaderExpanded(false)
      setZoomLevel(1)
      setPanOffset({ x: 0, y: 0 })
      setHoveredId(null)
      setDraggingId(null)
      setIsPanning(false)
      setDisplayNodes([])
      setError(null)
      setPreviousGraphState(null)
      localStorage.removeItem(LAST_SEEN_GRAPH_KEY)
      setScanStatus({ running: false, message: result.message, tone: 'info' }, 5000)
    } catch (resetError) {
      setScanStatus({ running: false, message: resetError.message, tone: 'neutral' })
    }
  }

  const stats = {
    nodes: graph?.nodes?.length ?? 0,
    edges: graph?.edges?.length ?? 0,
    newNodes: statusIsSeen ? 0 : nodes.filter((node) => node.status === 'new').length,
    changedNodes: statusIsSeen ? 0 : nodes.filter((node) => node.status === 'changed').length,
    newEdges: statusIsSeen ? 0 : links.filter((link) => link.status === 'new').length,
  }

  const graphBounds = useMemo(() => boundsFor(nodes), [nodes])
  const graphViewBox = useMemo(() => zoomedViewBox(graphBounds, zoomLevel, panOffset), [graphBounds, panOffset, zoomLevel])
  const graphUnitsPerPixel = 1 / (graphScaleFor(paneRef.current, graphViewBox) || 1)
  const visualNodeRadius = NODE_RADIUS * graphUnitsPerPixel
  const visualHitRadius = NODE_HIT_RADIUS * graphUnitsPerPixel
  const labelFontSize = NODE_LABEL_FONT_SIZE * graphUnitsPerPixel
  const labelStrokeWidth = NODE_LABEL_STROKE_WIDTH * graphUnitsPerPixel
  const visibleLabelIds = new Set(
    renderedNodes
      .filter(
        (node) =>
          (evolutionMode && node.status === 'new') || hoveredId === node.id || draggingId === node.id,
      )
      .map((node) => node.id),
  )
  const labelPlacements = labelPlacementsFor(renderedNodes, graphUnitsPerPixel, visibleLabelIds)
  const evolutionDisabled = graphHistory.length <= 1

  useEffect(() => {
    const pane = paneRef.current
    if (!pane) return undefined

    function handleMove(event) {
      handleGraphMouseMove(event)
    }

    function handleDown(event) {
      handleGraphMouseDown(event)
    }

    function handleLeave() {
      handleGraphMouseLeave()
    }

    function handleUp() {
      endGraphInteraction()
    }

    document.addEventListener('mousedown', handleDown, true)
    document.addEventListener('mousemove', handleMove, true)
    pane.addEventListener('mouseleave', handleLeave, true)
    window.addEventListener('mouseup', handleUp)

    return () => {
      document.removeEventListener('mousedown', handleDown, true)
      document.removeEventListener('mousemove', handleMove, true)
      pane.removeEventListener('mouseleave', handleLeave, true)
      window.removeEventListener('mouseup', handleUp)
    }
  }, [adjacency, graphViewBox, links, renderedNodes])

  return (
    <main className={`app-shell ${readerExpanded ? 'app-shell-reader-expanded' : ''}`}>
      <section className="topbar">
        <div className="topbar-title">
          <h1>Second Brain</h1>
        </div>
        <div className="toolbar">
          <button type="button" onClick={scanInput} disabled={scanState.running} title="Scan input directory">
            <Search size={18} />
            <span className="toolbar-label toolbar-label-inline">Scan</span>
          </button>
          <button type="button" onClick={resetNetwork} disabled={scanState.running} title="Reset generated network">
            <RotateCcw size={18} />
            <span className="toolbar-label toolbar-label-inline">Reset</span>
          </button>
          <button
            type="button"
            onClick={toggleEvolutionMode}
            className={`toolbar-evolution ${evolutionMode ? 'toolbar-active' : ''}`}
            title="See evolution"
          >
            <span className="toolbar-label">Evolution</span>
          </button>
          <button
            type="button"
            onClick={() => setCurrentGraphIndex((index) => Math.max(0, index - 1))}
            disabled={!evolutionMode || evolutionDisabled || currentGraphIndex === 0}
            title="Previous graph"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            type="button"
            onClick={() => setCurrentGraphIndex((index) => Math.min(graphHistory.length - 1, index + 1))}
            disabled={!evolutionMode || evolutionDisabled || currentGraphIndex >= graphHistory.length - 1}
            title="Next graph"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </section>

      <section className="stats-strip" aria-label="Graph stats">
        <span>{stats.nodes} nodes</span>
        <span>{stats.edges} links</span>
        <span>{stats.newNodes} new</span>
        <span>{stats.changedNodes} changed</span>
        <span>{stats.newEdges} new links</span>
        {evolutionMode ? (
          <span>
            Graph {currentGraphIndex + 1} / {Math.max(graphHistory.length, 1)}
          </span>
        ) : null}
        {scanState.message ? <span className={`scan-status scan-status-${scanState.tone}`}>{scanState.message}</span> : null}
      </section>

      <section className="workspace">
        <div ref={paneRef} className="graph-pane">
          {error ? (
            <div className="empty-state">{error}</div>
          ) : graph ? (
            <svg
              ref={svgRef}
              className={`network-graph ${draggingId ? 'network-graph-dragging' : ''} ${
                isPanning ? 'network-graph-panning' : ''
              } ${evolutionMode ? 'network-graph-evolution' : ''}`}
              viewBox={graphViewBox}
              role="img"
              aria-label="Second brain graph"
            >
              <g className="links-layer">
                {links.map((link) => {
                  const source = renderedNodes[link.sourceIndex]
                  const target = renderedNodes[link.targetIndex]
                  if (!source || !target) return null
                  return (
                    <line
                      key={link.id}
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                      className={`graph-link graph-link-${link.status} ${
                        selectedLink?.id === link.id ? 'graph-link-selected' : ''
                      }`}
                      stroke={link.color}
                      strokeWidth={link.width}
                    />
                  )
                })}
              </g>
              <g className="nodes-layer">
                {renderedNodes.map((node) => {
                  const label = labelPlacements.get(node.id) || {
                    x: (NODE_RADIUS + 16) * graphUnitsPerPixel,
                    y: 4 * graphUnitsPerPixel,
                    anchor: 'start',
                  }
                  return (
                    <g
                      key={node.id}
                      data-node-id={node.id}
                      className={`graph-node graph-node-${node.status} ${
                        selected?.id === node.id ? 'graph-node-selected' : ''
                      } ${hoveredId === node.id ? 'graph-node-hovered' : ''} ${
                        draggingId === node.id ? 'graph-node-dragging' : ''
                      }`}
                      transform={`translate(${node.x} ${node.y})`}
                    >
                      <circle className="graph-node-hit" r={visualHitRadius} />
                      <circle className="graph-node-mask" r={visualNodeRadius + 3 * graphUnitsPerPixel} />
                      <circle r={visualNodeRadius} fill={node.color} />
                      {node.type !== 'source' ? (
                        <text
                          x={label.x}
                          y={label.y}
                          textAnchor={label.anchor}
                          style={{
                            fontSize: labelFontSize,
                            strokeWidth: labelStrokeWidth,
                          }}
                        >
                          {node.label}
                        </text>
                      ) : null}
                    </g>
                  )
                })}
              </g>
            </svg>
          ) : graphLoadComplete ? (
            <div className="empty-state">Your second brain is currently empty</div>
          ) : null}
          {graph ? (
            <div className="zoom-controls" aria-label="Zoom controls">
              <button
                type="button"
                onClick={() => setZoomLevel((level) => Math.min(2.2, Number((level * 1.18).toFixed(3))))}
                title="Zoom in"
              >
                <Plus size={16} />
              </button>
              <button
                type="button"
                onClick={() => setZoomLevel((level) => Math.max(0.55, Number((level / 1.18).toFixed(3))))}
                title="Zoom out"
              >
                <Minus size={16} />
              </button>
            </div>
          ) : null}
        </div>

        <aside className="details-panel">
          {selectedLink ? (
            <LinkDetails
              link={selectedLink}
              source={renderedNodes[selectedLink.sourceIndex]}
              target={renderedNodes[selectedLink.targetIndex]}
              onPickNode={(node) => {
                setSelectedLink(null)
                setSelected(node)
              }}
              statusIsSeen={statusIsSeen}
            />
          ) : selected ? (
            <>
              <div className="details-heading-row">
                <h2>{selected.label}</h2>
                <span className={`status status-${displayStatus(selected.status, statusIsSeen)}`}>
                  {displayStatus(selected.status, statusIsSeen)}
                </span>
              </div>
              <div className="category-line">
                <span className="category-dot" style={{ background: selected.color }} />
                {selected.type}
              </div>
              <div className="markdown-toolbar">
                <span>{selected.path.replace(/^brain\//, '')}</span>
                <button type="button" onClick={() => setReaderExpanded((expanded) => !expanded)}>
                  {readerExpanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                </button>
              </div>
              {selectedMarkdownError ? (
                <div className="markdown-box markdown-box-error">{selectedMarkdownError}</div>
              ) : (
                <div className="markdown-box markdown-rendered">
                  {selectedMarkdown ? renderMarkdown(cleanMarkdownForDisplay(selectedMarkdown)) : <p>Loading Markdown...</p>}
                  <ConnectionReasons selected={selected} links={links} nodesById={nodesById} />
                </div>
              )}
            </>
          ) : (
            <>
              <h2>Nothing selected</h2>
              <p>Select a node to read its Markdown text and category.</p>
            </>
          )}
        </aside>
      </section>
    </main>
  )
}

function LinkDetails({ link, source, target, onPickNode, statusIsSeen }) {
  return (
    <>
      <div className="details-heading-row">
        <h2>Connection</h2>
        <span className={`status status-${displayStatus(link.status, statusIsSeen)}`}>
          {displayStatus(link.status, statusIsSeen)}
        </span>
      </div>
      <div className="category-line">{link.type.replace(/_/g, ' ')}</div>
      {link.shared_terms?.length ? (
        <div className="connection-terms">
          <span>Shared words</span>
          <div>
            {link.shared_terms.map((term) => (
              <code key={term}>{term}</code>
            ))}
          </div>
        </div>
      ) : null}
      <div className="link-detail">
        <button type="button" onClick={() => source && onPickNode(source)} disabled={!source}>
          <span className="link-detail-label">From</span>
          <strong>{source?.label || link.source}</strong>
          <small>{source?.type}</small>
        </button>
        <div className="link-detail-arrow">→</div>
        <button type="button" onClick={() => target && onPickNode(target)} disabled={!target}>
          <span className="link-detail-label">To</span>
          <strong>{target?.label || link.target}</strong>
          <small>{target?.type}</small>
        </button>
      </div>
    </>
  )
}

function ConnectionReasons({ selected, links, nodesById }) {
  if (!selected) return null
  const relatedLinks = links
    .filter((link) => link.source === selected.id || link.target === selected.id)
    .filter((link) => link.shared_terms?.length)
    .sort((left, right) => (right.score || 0) - (left.score || 0))

  if (!relatedLinks.length) return null

  return (
    <section className="connection-reasons">
      <h3>Why These Links Exist</h3>
      {relatedLinks.map((link) => {
        const otherId = link.source === selected.id ? link.target : link.source
        const otherNode = nodesById[otherId]
        return (
          <div className="connection-reason" key={link.id}>
            <strong>{otherNode?.label || otherId}</strong>
            <div>
              {link.shared_terms.map((term) => (
                <code key={term}>{term}</code>
              ))}
            </div>
          </div>
        )
      })}
    </section>
  )
}

function loadStoredGraphState() {
  try {
    const raw = localStorage.getItem(LAST_SEEN_GRAPH_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function renderMarkdown(markdown) {
  const lines = markdown.split(/\r?\n/)
  const blocks = []
  let paragraph = []
  let list = []
  let code = []
  let inCode = false
  let codeLanguage = ''

  function flushParagraph() {
    if (!paragraph.length) return
    blocks.push({ type: 'paragraph', text: paragraph.join(' ') })
    paragraph = []
  }

  function flushList() {
    if (!list.length) return
    blocks.push({ type: 'list', items: list })
    list = []
  }

  function flushCode() {
    blocks.push({ type: 'code', language: codeLanguage, text: code.join('\n') })
    code = []
    codeLanguage = ''
  }

  for (const line of lines) {
    const fence = line.match(/^```(\w+)?\s*$/)
    if (fence) {
      if (inCode) {
        flushCode()
        inCode = false
      } else {
        flushParagraph()
        flushList()
        inCode = true
        codeLanguage = fence[1] || ''
      }
      continue
    }

    if (inCode) {
      code.push(line)
      continue
    }

    if (!line.trim()) {
      flushParagraph()
      flushList()
      continue
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/)
    if (heading) {
      flushParagraph()
      flushList()
      blocks.push({ type: 'heading', depth: heading[1].length, text: heading[2] })
      continue
    }

    const item = line.match(/^\s*[-*]\s+(.+)$/)
    if (item) {
      flushParagraph()
      list.push(item[1])
      continue
    }

    paragraph.push(line.trim())
  }

  if (inCode) flushCode()
  flushParagraph()
  flushList()

  return blocks.map((block, index) => {
    if (block.type === 'heading') {
      const Tag = `h${Math.min(block.depth + 2, 5)}`
      return <Tag key={index}>{renderInlineMarkdown(block.text)}</Tag>
    }
    if (block.type === 'list') {
      return (
        <ul key={index}>
          {block.items.map((item, itemIndex) => (
            <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      )
    }
    if (block.type === 'code') {
      return (
        <pre key={index}>
          <code>{block.text}</code>
        </pre>
      )
    }
    return <p key={index}>{renderInlineMarkdown(block.text)}</p>
  })
}

function cleanMarkdownForDisplay(markdown) {
  return markdown
    .replace(/^#{1,6}\s*(Source Trace|Related|Brain links that should probably exist later):?\s*\n[\s\S]*?(?=^#{1,6}\s+|(?![\s\S]))/gim, '')
    .replace(/^Brain links that should probably exist later:\s*\n(?:^[ \t]*[-*].*(?:\n|$)|^[ \t]*\n)*/gim, '')
    .trim()
}

function renderInlineMarkdown(text) {
  const parts = []
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g
  let cursor = 0
  let match

  while ((match = pattern.exec(text))) {
    if (match.index > cursor) parts.push(text.slice(cursor, match.index))
    const token = match[0]

    if (token.startsWith('**')) {
      parts.push(<strong key={parts.length}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('`')) {
      parts.push(<code key={parts.length}>{token.slice(1, -1)}</code>)
    } else {
      const link = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
      parts.push(
        <a key={parts.length} href={link[2]} target="_blank" rel="noreferrer">
          {link[1]}
        </a>,
      )
    }
    cursor = pattern.lastIndex
  }

  if (cursor < text.length) parts.push(text.slice(cursor))
  return parts
}

function snapshotGraphState(graph) {
  return {
    build_id: graph.build_id,
    nodes: Object.fromEntries(graph.nodes.map((node) => [node.id, node.hash])),
    edges: Object.fromEntries(graph.edges.map((edge) => [edge.id, edge.hash])),
  }
}

function sanitizeGraph(graph) {
  if (!graph) return graph
  return {
    ...graph,
    nodes: (graph.nodes || []).filter((node) => !isExcludedNodeId(node.id)),
    edges: (graph.edges || []).filter(
      (edge) => !isExcludedNodeId(edge.source) && !isExcludedNodeId(edge.target),
    ),
  }
}

function isExcludedNodeId(id) {
  return EXCLUDED_NODE_IDS.has(id) || EXCLUDED_NODE_PREFIXES.some((prefix) => id.startsWith(prefix))
}

function normalizeHistory(historyPayload, currentGraph, options = {}) {
  const { simulateEvolution = true } = options
  const historyGraphs = Array.isArray(historyPayload)
    ? historyPayload
    : Array.isArray(historyPayload?.graphs)
      ? historyPayload.graphs
      : []
  const byBuildId = new Map()

  for (const historyGraph of historyGraphs) {
    if (historyGraph?.build_id) {
      byBuildId.set(historyGraph.build_id, sanitizeGraph(historyGraph))
    }
  }

  byBuildId.set(currentGraph.build_id, currentGraph)
  const graphs = [...byBuildId.values()].sort((left, right) => {
    const leftTime = Date.parse(left.generated_at || '')
    const rightTime = Date.parse(right.generated_at || '')
    if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) return 0
    return leftTime - rightTime
  })

  return simulateEvolution && shouldUseSimulatedEvolution(graphs, currentGraph) ? simulatedHistoryFor(currentGraph) : graphs
}

function scanEvolutionHistoryFor(previousGraph, currentGraph, forcedNewNodeIds = []) {
  if (!previousGraph?.nodes?.length || !currentGraph?.nodes?.length) return [currentGraph]

  const previousNodeIds = new Set(previousGraph.nodes.map((node) => node.id))
  const previousEdgeIds = new Set((previousGraph.edges || []).map((edge) => edge.id))
  const currentNodeIds = new Set(currentGraph.nodes.map((node) => node.id))
  const currentEdgeIds = new Set((currentGraph.edges || []).map((edge) => edge.id))
  const forcedNewNodes = new Set(forcedNewNodeIds.filter((id) => currentNodeIds.has(id)))
  const beforeGraph = sanitizeGraph({
    ...previousGraph,
    nodes: previousGraph.nodes
      .filter((node) => currentNodeIds.has(node.id) && !forcedNewNodes.has(node.id))
      .map((node) => ({ ...node, status: currentGraphNodeStatus(node, currentGraph, previousNodeIds) })),
    edges: (previousGraph.edges || [])
      .filter((edge) => currentEdgeIds.has(edge.id) && !forcedNewNodes.has(edge.source) && !forcedNewNodes.has(edge.target))
      .map((edge) => ({ ...edge, status: currentGraphEdgeStatus(edge, currentGraph, previousEdgeIds) })),
  })
  const afterGraph = sanitizeGraph({
    ...currentGraph,
    nodes: currentGraph.nodes.map((node) => ({
      ...node,
      status: forcedNewNodes.has(node.id) || !previousNodeIds.has(node.id) ? 'new' : node.status || 'unchanged',
    })),
    edges: (currentGraph.edges || []).map((edge) => ({
      ...edge,
      status:
        forcedNewNodes.has(edge.source) || forcedNewNodes.has(edge.target) || !previousEdgeIds.has(edge.id)
          ? 'new'
          : edge.status || 'unchanged',
    })),
  })

  if (beforeGraph.build_id === afterGraph.build_id) {
    return [afterGraph]
  }
  return [beforeGraph, afterGraph]
}

function currentGraphNodeStatus(node, currentGraph, previousNodeIds) {
  if (!previousNodeIds.has(node.id)) return 'new'
  const current = currentGraph.nodes.find((candidate) => candidate.id === node.id)
  return current?.status || 'unchanged'
}

function currentGraphEdgeStatus(edge, currentGraph, previousEdgeIds) {
  if (!previousEdgeIds.has(edge.id)) return 'new'
  const current = (currentGraph.edges || []).find((candidate) => candidate.id === edge.id)
  return current?.status || 'unchanged'
}

function shouldUseSimulatedEvolution(graphs, currentGraph) {
  if (graphs.length < 4) return true
  const latestCount = currentGraph.nodes?.length || 0
  const nodeCounts = new Set(graphs.map((historyGraph) => historyGraph.nodes?.length || 0))
  const hasGrowthIntoLatest = graphs.some((historyGraph) => (historyGraph.nodes?.length || 0) < latestCount)
  return nodeCounts.size < 3 || !hasGrowthIntoLatest
}

function simulatedHistoryFor(currentGraph) {
  const nodes = currentGraph.nodes || []
  const edges = currentGraph.edges || []
  if (!nodes.length) return [currentGraph]

  const orderedNodeIds = growthOrderFor(nodes, edges)
  const steps = frameTargetsFor(nodes.length)
  const currentTime = Date.parse(currentGraph.generated_at || '') || Date.now()
  let previousNodeIds = new Set()
  let previousEdgeIds = new Set()

  return steps.map((nodeCount, stepIndex) => {
    const includedIds = new Set(orderedNodeIds.slice(0, nodeCount))
    const stepNodes = nodes
      .filter((node) => includedIds.has(node.id))
      .map((node) => ({
        ...node,
        status: previousNodeIds.has(node.id) ? 'unchanged' : 'new',
      }))
    const stepEdges = edges
      .filter((edge) => includedIds.has(edge.source) && includedIds.has(edge.target))
      .map((edge) => ({
        ...edge,
        status: previousEdgeIds.has(edge.id) ? 'unchanged' : 'new',
      }))
    const stepEdgeIds = new Set(stepEdges.map((edge) => edge.id))

    previousNodeIds = includedIds
    previousEdgeIds = stepEdgeIds

    return {
      ...currentGraph,
      build_id: stepIndex === steps.length - 1 ? currentGraph.build_id : `${currentGraph.build_id}-evolution-${stepIndex + 1}`,
      generated_at: new Date(currentTime - (steps.length - stepIndex - 1) * 60_000).toISOString(),
      nodes: stepNodes,
      edges: stepEdges,
      simulated: true,
    }
  })
}

function frameTargetsFor(nodeCount) {
  const ratios = [0.18, 0.34, 0.52, 0.72, 0.88, 1]
  return [
    ...new Set(
      ratios.map((ratio) => {
        if (ratio === 1) return nodeCount
        return Math.max(1, Math.min(nodeCount, Math.ceil(nodeCount * ratio)))
      }),
    ),
  ]
}

function growthOrderFor(nodes, edges) {
  const ids = new Set(nodes.map((node) => node.id))
  const adjacency = new Map(nodes.map((node) => [node.id, new Set()]))
  const degree = new Map(nodes.map((node) => [node.id, 0]))

  for (const edge of edges) {
    if (!ids.has(edge.source) || !ids.has(edge.target)) continue
    adjacency.get(edge.source).add(edge.target)
    adjacency.get(edge.target).add(edge.source)
    degree.set(edge.source, (degree.get(edge.source) || 0) + 1)
    degree.set(edge.target, (degree.get(edge.target) || 0) + 1)
  }

  const orderedIds = []
  const included = new Set()

  function compareCandidates(left, right) {
    return (
      (degree.get(right) || 0) - (degree.get(left) || 0) ||
      hashToUnit(left) - hashToUnit(right) ||
      left.localeCompare(right)
    )
  }

  function add(id) {
    if (!id || included.has(id)) return
    included.add(id)
    orderedIds.push(id)
  }

  add(nodes.map((node) => node.id).sort(compareCandidates)[0])

  while (orderedIds.length < nodes.length) {
    const frontier = [...included]
      .flatMap((id) => [...(adjacency.get(id) || [])])
      .filter((id) => !included.has(id))
      .sort(compareCandidates)

    if (frontier.length) {
      add(frontier[0])
      continue
    }

    add(
      nodes
        .map((node) => node.id)
        .filter((id) => !included.has(id))
        .sort(compareCandidates)[0],
    )
  }

  return orderedIds
}

function statusForNode(node, previousGraphState) {
  if (!previousGraphState) return node.status
  const previousHash = previousGraphState.nodes?.[node.id]
  if (!previousHash) return 'new'
  return previousHash === node.hash ? 'unchanged' : 'changed'
}

function statusForEdge(edge, previousGraphState) {
  if (!previousGraphState) return edge.status
  return previousGraphState.edges?.[edge.id] ? 'unchanged' : 'new'
}

function stableLayout(rawNodes, rawEdges = []) {
  const communities = communitiesFor(rawNodes, rawEdges)
  const communityIds = [...new Set(rawNodes.map((node) => communities.get(node.id) || node.id))].sort()
  const communityRadius = communityIds.length <= 1 ? 0 : Math.min(220, 76 + communityIds.length * 14)
  const communityCenterById = new Map(
    communityIds.map((communityId, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(communityIds.length, 1)
      return [communityId, { x: Math.cos(angle) * communityRadius, y: Math.sin(angle) * communityRadius }]
    }),
  )

  const nodes = rawNodes
    .slice()
    .sort((left, right) => left.id.localeCompare(right.id))
    .map((node, index) => {
      const angle = hashToUnit(node.id) * Math.PI * 2
      const communityId = communities.get(node.id) || node.id
      const center = communityCenterById.get(communityId) || { x: 0, y: 0 }
      const radius = 24 + 8 * Math.sqrt(index + 1)
      return {
        ...node,
        communityId,
        vx: 0,
        vy: 0,
        x: center.x + Math.cos(angle) * radius,
        y: center.y + Math.sin(angle) * radius,
      }
    })

  const indexById = new Map(nodes.map((node, index) => [node.id, index]))
  const edges = rawEdges
    .map((edge) => [indexById.get(edge.source), indexById.get(edge.target)])
    .filter(([source, target]) => Number.isInteger(source) && Number.isInteger(target) && source !== target)

  const iterations = 380
  const idealDistance = 58

  for (let iteration = 0; iteration < iterations; iteration += 1) {
    const cooling = 1 - iteration / iterations

    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
        const left = nodes[leftIndex]
        const right = nodes[rightIndex]
        const dx = right.x - left.x || 0.01
        const dy = right.y - left.y || 0.01
        const distanceSq = dx * dx + dy * dy
        const distance = Math.sqrt(distanceSq)
        const sameCommunity = left.communityId === right.communityId
        const force = Math.min(9, (sameCommunity ? 820 : 1500) / distanceSq)
        const fx = (dx / distance) * force
        const fy = (dy / distance) * force
        left.vx -= fx
        left.vy -= fy
        right.vx += fx
        right.vy += fy
      }
    }

    for (const [sourceIndex, targetIndex] of edges) {
      const source = nodes[sourceIndex]
      const target = nodes[targetIndex]
      const dx = target.x - source.x
      const dy = target.y - source.y
      const distance = Math.sqrt(dx * dx + dy * dy) || 1
      const force = (distance - idealDistance) * 0.092
      const fx = (dx / distance) * force
      const fy = (dy / distance) * force
      source.vx += fx
      source.vy += fy
      target.vx -= fx
      target.vy -= fy
    }

    for (const node of nodes) {
      const center = communityCenterById.get(node.communityId) || { x: 0, y: 0 }
      node.vx += (center.x - node.x) * 0.009
      node.vy += (center.y - node.y) * 0.009
      node.vx += -node.x * 0.0014
      node.vy += -node.y * 0.0014
      node.x += node.vx * 0.2 * cooling
      node.y += node.vy * 0.2 * cooling
      node.vx *= 0.58
      node.vy *= 0.58
    }
  }

  return nodes.map(({ vx, vy, ...node }) => ({
    ...node,
    x: Math.round(node.x),
    y: Math.round(node.y),
  }))
}

function communitiesFor(rawNodes, rawEdges) {
  const nodeIds = rawNodes.map((node) => node.id).sort()
  const fullAdjacency = adjacencyFor(rawNodes, rawEdges)
  const communityById = new Map()
  const visited = new Set()

  for (const id of nodeIds) {
    if (visited.has(id)) continue
    const stack = [id]
    const component = []
    visited.add(id)

    while (stack.length) {
      const current = stack.pop()
      component.push(current)
      for (const neighbor of fullAdjacency.get(current) || []) {
        if (visited.has(neighbor)) continue
        visited.add(neighbor)
        stack.push(neighbor)
      }
    }

    const communityId = component.slice().sort()[0]
    for (const componentId of component) {
      communityById.set(componentId, communityId)
    }
  }
  return communityById
}

function adjacencyFor(rawNodes, rawEdges) {
  const adjacency = new Map(rawNodes.map((node) => [node.id, new Set()]))
  for (const edge of rawEdges) {
    adjacency.get(edge.source)?.add(edge.target)
    adjacency.get(edge.target)?.add(edge.source)
  }
  return adjacency
}

function pullConnectedNodes(nodes, draggedId, dx, dy, adjacency) {
  const directNeighbors = adjacency.get(draggedId) || new Set()
  const secondHopNeighbors = new Set()
  for (const neighbor of directNeighbors) {
    for (const secondHop of adjacency.get(neighbor) || []) {
      if (secondHop !== draggedId && !directNeighbors.has(secondHop)) {
        secondHopNeighbors.add(secondHop)
      }
    }
  }

  return nodes.map((node) => {
    let influence = 0
    if (node.id === draggedId) influence = 1
    else if (directNeighbors.has(node.id)) influence = 0.58
    else if (secondHopNeighbors.has(node.id)) influence = 0.22
    if (!influence) return node
    return {
      ...node,
      x: node.x + dx * influence,
      y: node.y + dy * influence,
    }
  })
}

function moveAllNodes(nodes, dx, dy) {
  if (!dx && !dy) return nodes
  return nodes.map((node) => ({
    ...node,
    x: node.x + dx,
    y: node.y + dy,
  }))
}

function nearestNodeAtPoint(point, nodes, pane, viewBox) {
  const unitsPerPixel = 1 / (graphScaleFor(pane, viewBox) || 1)
  const hitRadius = NODE_HIT_RADIUS * unitsPerPixel
  let nearest = null
  let nearestDistance = Infinity

  for (const node of nodes) {
    const dx = point.x - node.x
    const dy = point.y - node.y
    const distance = Math.sqrt(dx * dx + dy * dy)
    if (distance <= hitRadius && distance < nearestDistance) {
      nearest = node
      nearestDistance = distance
    }
  }

  return nearest
}

function nearestLinkAtPoint(point, links, nodes, pane, viewBox) {
  const unitsPerPixel = 1 / (graphScaleFor(pane, viewBox) || 1)
  const hitDistance = 9 * unitsPerPixel
  let nearest = null
  let nearestDistance = Infinity

  for (const link of links) {
    const source = nodes[link.sourceIndex]
    const target = nodes[link.targetIndex]
    if (!source || !target) continue
    const distance = distanceToSegment(point, source, target)
    if (distance <= hitDistance && distance < nearestDistance) {
      nearest = link
      nearestDistance = distance
    }
  }

  return nearest
}

function distanceToSegment(point, start, end) {
  const dx = end.x - start.x
  const dy = end.y - start.y
  if (!dx && !dy) return Math.hypot(point.x - start.x, point.y - start.y)
  const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)))
  const x = start.x + t * dx
  const y = start.y + t * dy
  return Math.hypot(point.x - x, point.y - y)
}

function isInsidePane(event, pane) {
  const rect = pane?.getBoundingClientRect()
  if (!rect) return false
  return (
    event.clientX >= rect.left &&
    event.clientX <= rect.right &&
    event.clientY >= rect.top &&
    event.clientY <= rect.bottom
  )
}

function graphScaleFor(pane, viewBox) {
  const rect = pane?.getBoundingClientRect()
  const [, , width, height] = viewBox.split(' ').map(Number)
  if (!rect?.width || !rect?.height || !width || !height) return null
  return Math.min(rect.width / width, rect.height / height)
}

function graphPointFor(event, pane, viewBox) {
  const rect = pane?.getBoundingClientRect()
  const [x, y, width, height] = viewBox.split(' ').map(Number)
  if (!rect?.width || !rect?.height || !width || !height) return null
  const scale = Math.min(rect.width / width, rect.height / height)
  const drawnWidth = width * scale
  const drawnHeight = height * scale
  const offsetX = (rect.width - drawnWidth) / 2
  const offsetY = (rect.height - drawnHeight) / 2
  return {
    x: x + (event.clientX - rect.left - offsetX) / scale,
    y: y + (event.clientY - rect.top - offsetY) / scale,
  }
}

function hashToUnit(value) {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0) / 4294967295
}

function boundsFor(nodes) {
  if (!nodes.length) return { viewBox: '-500 -500 1000 1000' }
  const padding = 230
  const xs = nodes.map((node) => node.x)
  const ys = nodes.map((node) => node.y)
  const minX = Math.min(...xs) - padding
  const maxX = Math.max(...xs) + padding
  const minY = Math.min(...ys) - padding
  const maxY = Math.max(...ys) + padding
  return {
    viewBox: `${minX} ${minY} ${maxX - minX} ${maxY - minY}`,
  }
}

function zoomedViewBox(bounds, zoomLevel, panOffset) {
  const [x, y, width, height] = bounds.viewBox.split(' ').map(Number)
  const nextWidth = width / zoomLevel
  const nextHeight = height / zoomLevel
  const nextX = x + (width - nextWidth) / 2 + panOffset.x
  const nextY = y + (height - nextHeight) / 2 + panOffset.y
  return `${nextX} ${nextY} ${nextWidth} ${nextHeight}`
}
