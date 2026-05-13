import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { AnalysisArtifact } from "../types";

type Props = {
  analysis: AnalysisArtifact;
  replayTime: number;
  selectedFailureKey: string | null;
  onSelectFailure: (failureKey: string, timestamp: number) => void;
};

function failureKey(failure: AnalysisArtifact["failures"][number]) {
  return `${failure.failure_type}-${failure.timestamp}`;
}

export function TrajectoryScene({ analysis, replayTime, selectedFailureKey, onSelectFailure }: Props) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const markerRef = useRef<THREE.Mesh | null>(null);
  const failureRefs = useRef<THREE.Mesh[]>([]);

  const samples = analysis.run.samples;
  const points = useMemo(
    () => samples.map((sample) => new THREE.Vector3(sample.pose.x, sample.pose.y, 0)),
    [samples],
  );
  const bounds = useMemo(() => buildBounds(analysis), [analysis]);

  useEffect(() => {
    if (!rootRef.current) return;
    const root = rootRef.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#f7f8fa");

    const width = root.clientWidth || 800;
    const height = root.clientHeight || 420;
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);
    camera.position.set(0, 0, 10);

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    root.appendChild(renderer.domElement);
    failureRefs.current = [];

    fitCamera(camera, bounds, width, height);

    const gridSize = Math.max(bounds.width, bounds.height, 10);
    const grid = new THREE.GridHelper(gridSize, 16, "#b9c1cc", "#e1e5eb");
    grid.rotation.x = Math.PI / 2;
    grid.position.set(bounds.centerX, bounds.centerY, -0.01);
    scene.add(grid);

    if (analysis.run.costmap) {
      const { width: cellsX, height: cellsY, resolution, origin, data } = analysis.run.costmap;
      const maxCells = 12000;
      const stride = Math.max(1, Math.ceil((cellsX * cellsY) / maxCells));
      for (let y = 0; y < cellsY; y += 1) {
        for (let x = 0; x < cellsX; x += 1) {
          if ((y * cellsX + x) % stride !== 0) continue;
          const value = data[y * cellsX + x] ?? 0;
          if (value <= 0) continue;
          const color = new THREE.Color().setHSL(0.12 - Math.min(value, 100) / 1000, 0.78, 0.52);
          const cell = new THREE.Mesh(
            new THREE.PlaneGeometry(resolution, resolution),
            new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.38 }),
          );
          cell.position.set(origin.x + (x + 0.5) * resolution, origin.y + (y + 0.5) * resolution, 0.02);
          scene.add(cell);
        }
      }
    }

    const planPoints = analysis.run.planned_path.map((p) => new THREE.Vector3(p.x, p.y, 0.01));
    if (planPoints.length > 1) {
      const planLine = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(planPoints),
        new THREE.LineBasicMaterial({ color: "#276ef1", linewidth: 2 }),
      );
      scene.add(planLine);
    }

    if (points.length > 1) {
      const trajectory = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(points.map((p) => p.clone().setZ(0.03))),
        new THREE.LineBasicMaterial({ color: "#0b7a53", linewidth: 3 }),
      );
      scene.add(trajectory);
    }

    const start = samples[0];
    const finish = samples.at(-1);
    if (start) scene.add(makePoseMarker(start.pose.x, start.pose.y, start.pose.yaw, "#276ef1", "start"));
    if (finish) scene.add(makePoseMarker(finish.pose.x, finish.pose.y, finish.pose.yaw, "#0b7a53", "finish"));
    const goal = analysis.run.goal_pose ?? analysis.run.goal;
    if (goal) {
      const goalMarker = new THREE.Mesh(
        new THREE.RingGeometry(0.22, 0.32, 28),
        new THREE.MeshBasicMaterial({ color: "#c2410c", transparent: true, opacity: 0.9 }),
      );
      goalMarker.position.set(goal.x, goal.y, 0.09);
      scene.add(goalMarker);
    }

    for (const failure of analysis.failures) {
      const nearest = samples.reduce((best, sample) =>
        Math.abs(sample.t - failure.timestamp) < Math.abs(best.t - failure.timestamp) ? sample : best,
      samples[0]);
      const geometry = new THREE.RingGeometry(0.12, 0.18, 24);
      const material = new THREE.MeshBasicMaterial({ color: failure.severity === "high" ? "#c92a2a" : "#e67700" });
      const ring = new THREE.Mesh(geometry, material);
      ring.position.set(nearest.pose.x, nearest.pose.y, 0.06);
      ring.userData = { failureKey: failureKey(failure), timestamp: failure.timestamp };
      failureRefs.current.push(ring);
      scene.add(ring);
    }

    const marker = new THREE.Mesh(
      new THREE.CircleGeometry(0.16, 32),
      new THREE.MeshBasicMaterial({ color: "#111827" }),
    );
    marker.position.z = 0.12;
    markerRef.current = marker;
    scene.add(marker);

    const resize = () => {
      const nextWidth = root.clientWidth || 800;
      const nextHeight = root.clientHeight || 420;
      fitCamera(camera, bounds, nextWidth, nextHeight);
      renderer.setSize(nextWidth, nextHeight);
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(root);
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const pointerDown = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(failureRefs.current, false)[0];
      if (!hit) return;
      const key = String(hit.object.userData.failureKey);
      const timestamp = Number(hit.object.userData.timestamp);
      onSelectFailure(key, timestamp);
    };
    window.addEventListener("resize", resize);
    renderer.domElement.addEventListener("pointerdown", pointerDown);

    let frame = 0;
    const render = () => {
      frame = requestAnimationFrame(render);
      renderer.render(scene, camera);
    };
    render();

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointerdown", pointerDown);
      renderer.dispose();
      root.removeChild(renderer.domElement);
    };
  }, [analysis, bounds, onSelectFailure, points, samples]);

  useEffect(() => {
    if (!markerRef.current || samples.length === 0) return;
    const sample = samples.reduce((best, candidate) =>
      Math.abs(candidate.t - replayTime) < Math.abs(best.t - replayTime) ? candidate : best,
    samples[0]);
    markerRef.current.position.x = sample.pose.x;
    markerRef.current.position.y = sample.pose.y;
  }, [replayTime, samples]);

  useEffect(() => {
    for (const ring of failureRefs.current) {
      const material = ring.material as THREE.MeshBasicMaterial;
      const isSelected = ring.userData.failureKey === selectedFailureKey;
      ring.scale.setScalar(isSelected ? 1.45 : 1);
      material.opacity = isSelected ? 1 : 0.82;
      material.transparent = true;
    }
  }, [selectedFailureKey]);

  return <div className="trajectoryScene" ref={rootRef} />;
}

function makePoseMarker(x: number, y: number, yaw: number, color: string, name: string) {
  const marker = new THREE.Mesh(
    new THREE.ConeGeometry(0.22, 0.42, 3),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.94 }),
  );
  marker.name = name;
  marker.position.set(x, y, 0.1);
  marker.rotation.z = yaw - Math.PI / 2;
  return marker;
}

function buildBounds(analysis: AnalysisArtifact) {
  const coordinates = [
    ...analysis.run.samples.map((sample) => sample.pose),
    ...analysis.run.planned_path,
  ];
  if (analysis.run.goal) coordinates.push(analysis.run.goal);
  if (analysis.run.goal_pose) coordinates.push(analysis.run.goal_pose);
  if (analysis.run.costmap) {
    const { origin, width, height, resolution } = analysis.run.costmap;
    coordinates.push(origin, { x: origin.x + width * resolution, y: origin.y + height * resolution });
  }
  if (coordinates.length === 0) {
    return { minX: -1, maxX: 1, minY: -1, maxY: 1, centerX: 0, centerY: 0, width: 2, height: 2 };
  }
  const minX = Math.min(...coordinates.map((point) => point.x));
  const maxX = Math.max(...coordinates.map((point) => point.x));
  const minY = Math.min(...coordinates.map((point) => point.y));
  const maxY = Math.max(...coordinates.map((point) => point.y));
  const width = Math.max(maxX - minX, 2);
  const height = Math.max(maxY - minY, 2);
  return {
    minX,
    maxX,
    minY,
    maxY,
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2,
    width,
    height,
  };
}

function fitCamera(
  camera: THREE.OrthographicCamera,
  bounds: ReturnType<typeof buildBounds>,
  viewportWidth: number,
  viewportHeight: number,
) {
  const aspect = Math.max(viewportWidth / Math.max(viewportHeight, 1), 0.1);
  const paddedWidth = bounds.width * 1.18;
  const paddedHeight = bounds.height * 1.18;
  const viewHeight = Math.max(paddedHeight, paddedWidth / aspect, 3);
  const viewWidth = viewHeight * aspect;
  camera.left = bounds.centerX - viewWidth / 2;
  camera.right = bounds.centerX + viewWidth / 2;
  camera.top = bounds.centerY + viewHeight / 2;
  camera.bottom = bounds.centerY - viewHeight / 2;
  camera.updateProjectionMatrix();
}
