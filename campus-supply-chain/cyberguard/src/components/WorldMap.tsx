import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import * as topojson from 'topojson-client';
import { AttackEvent } from '../types';

interface WorldMapProps {
  attacks: AttackEvent[];
}

const WorldMap: React.FC<WorldMapProps> = ({ attacks }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [worldData, setWorldData] = useState<any>(null);

  useEffect(() => {
    fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
      .then(response => response.json())
      .then(data => {
        setWorldData(topojson.feature(data, data.objects.countries));
      });
  }, []);

  const animatedAttacksRef = useRef<Set<string>>(new Set());

  // Static Map Drawing
  useEffect(() => {
    if (!worldData || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    svg.selectAll('*').remove();

    // Define gradients and filters
    const defs = svg.append('defs');
    
    const radialGradient = defs.append('radialGradient')
      .attr('id', 'map-gradient')
      .attr('cx', '50%')
      .attr('cy', '50%')
      .attr('r', '50%');
    
    radialGradient.append('stop')
      .attr('offset', '0%')
      .attr('stop-color', '#1e293b');
    
    radialGradient.append('stop')
      .attr('offset', '100%')
      .attr('stop-color', '#020617');

    svg.append('rect')
      .attr('width', width)
      .attr('height', height)
      .attr('fill', 'url(#map-gradient)');
    
    const glowFilter = defs.append('filter')
      .attr('id', 'glow')
      .attr('x', '-20%')
      .attr('y', '-20%')
      .attr('width', '140%')
      .attr('height', '140%');
    
    glowFilter.append('feGaussianBlur')
      .attr('stdDeviation', '2')
      .attr('result', 'blur');
    
    glowFilter.append('feComposite')
      .attr('in', 'SourceGraphic')
      .attr('in2', 'blur')
      .attr('operator', 'over');

    const projection = d3.geoMercator()
      .scale(width / 6.2)
      .translate([width / 2, height / 1.4]);

    const path = d3.geoPath().projection(projection);

    // Background Grid
    const gridGroup = svg.append('g').attr('class', 'grid');
    const gridSize = 40;
    for (let x = 0; x <= width; x += gridSize) {
      gridGroup.append('line')
        .attr('x1', x).attr('y1', 0).attr('x2', x).attr('y2', height)
        .attr('stroke', 'rgba(255,255,255,0.03)').attr('stroke-width', 1);
    }
    for (let y = 0; y <= height; y += gridSize) {
      gridGroup.append('line')
        .attr('x1', 0).attr('y1', y).attr('x2', width).attr('y2', y)
        .attr('stroke', 'rgba(255,255,255,0.03)').attr('stroke-width', 1);
    }

    // Graticules
    const graticule = d3.geoGraticule();
    svg.append('path')
      .datum(graticule())
      .attr('class', 'graticule')
      .attr('d', path as any)
      .attr('fill', 'none')
      .attr('stroke', 'rgba(255,255,255,0.05)')
      .attr('stroke-width', 0.5);

    // Draw map
    svg.append('g')
      .attr('class', 'map-layer')
      .selectAll('path')
      .data(worldData.features)
      .enter()
      .append('path')
      .attr('d', path as any)
      .attr('fill', '#0f172a') // Darker navy for land
      .attr('stroke', '#1e293b') // Slate border
      .attr('stroke-width', 1)
      .on('mouseover', function() {
        d3.select(this).attr('fill', '#1e293b').attr('stroke', '#3b82f6');
      })
      .on('mouseout', function() {
        d3.select(this).attr('fill', '#0f172a').attr('stroke', '#1e293b');
      });

    // Draw target point (HQ)
    const targetPos = projection([125.3235, 43.8170]); // Changchun
    if (targetPos) {
      const g = svg.append('g').attr('class', 'target-layer');
      
      // Outer rings
      g.append('circle')
        .attr('cx', targetPos[0])
        .attr('cy', targetPos[1])
        .attr('r', 15)
        .attr('fill', 'none')
        .attr('stroke', '#3b82f6')
        .attr('stroke-width', 1)
        .attr('opacity', 0.3)
        .append('animate')
        .attr('attributeName', 'r')
        .attr('from', '10')
        .attr('to', '25')
        .attr('dur', '2s')
        .attr('repeatCount', 'indefinite');

      g.append('circle')
        .attr('cx', targetPos[0])
        .attr('cy', targetPos[1])
        .attr('r', 5)
        .attr('fill', '#3b82f6')
        .attr('filter', 'url(#glow)');
      
      // Label
      g.append('text')
        .attr('x', targetPos[0] + 12)
        .attr('y', targetPos[1] - 12)
        .text('校园物资供应链安全中心')
        .attr('fill', '#60a5fa')
        .attr('font-size', '12px')
        .attr('font-family', 'Inter, sans-serif')
        .attr('font-weight', '900')
        .attr('filter', 'url(#glow)');
    }

    // Create groups for attacks
    svg.append('g').attr('class', 'lines-layer');
    svg.append('g').attr('class', 'labels-layer');
    svg.append('g').attr('class', 'impact-layer');

  }, [worldData]);

  // Dynamic Attack Animations
  useEffect(() => {
    if (!worldData || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;
    
    const projection = d3.geoMercator()
      .scale(width / 6.2)
      .translate([width / 2, height / 1.4]);

    const lineGroup = svg.select('.lines-layer');
    const labelGroup = svg.select('.labels-layer');
    const impactGroup = svg.select('.impact-layer');

    attacks.forEach((attack) => {
      // Skip if already animated
      if (animatedAttacksRef.current.has(attack.id)) return;
      animatedAttacksRef.current.add(attack.id);

      const source = projection([attack.sourceLocation.lng, attack.sourceLocation.lat]);
      const target = projection([attack.targetLocation.lng, attack.targetLocation.lat]);

      if (source && target) {
        const [x1, y1] = source;
        const [x2, y2] = target;

        // Source city label
        const sourceLabel = labelGroup.append('g')
          .attr('opacity', 0);

        sourceLabel.append('rect')
          .attr('x', x1 - 40)
          .attr('y', y1 - 28)
          .attr('width', 80)
          .attr('height', 16)
          .attr('rx', 4)
          .attr('fill', 'rgba(0,0,0,0.6)')
          .attr('backdrop-filter', 'blur(4px)');

        sourceLabel.append('text')
          .attr('x', x1)
          .attr('y', y1 - 16)
          .attr('text-anchor', 'middle')
          .text(attack.sourceLocation.city)
          .attr('fill', '#fff')
          .attr('font-size', '11px')
          .attr('font-family', 'Inter, sans-serif')
          .attr('font-weight', 'bold')
          .attr('filter', 'url(#glow)');

        sourceLabel.append('circle')
          .attr('cx', x1)
          .attr('cy', y1)
          .attr('r', 4)
          .attr('fill', '#fff')
          .attr('filter', 'url(#glow)');

        // Varied curvature
        const dx = x2 - x1;
        const dy = y2 - y1;
        const dr = Math.sqrt(dx * dx + dy * dy) * (1 + Math.random());
        const pathData = `M${x1},${y1}A${dr},${dr} 0 0,1 ${x2},${y2}`;

        const color = attack.severity === '致命' ? '#ef4444' : 
                     attack.severity === '高危' ? '#f59e0b' : '#10b981';

        const pathEl = lineGroup.append('path')
          .attr('d', pathData)
          .attr('fill', 'none')
          .attr('stroke', color)
          .attr('stroke-width', 2)
          .attr('filter', 'url(#glow)')
          .attr('opacity', 0.8)
          .attr('stroke-dasharray', function() { return (this as any).getTotalLength(); })
          .attr('stroke-dashoffset', function() { return (this as any).getTotalLength(); });

        const duration = 2500 + Math.random() * 1500; // Slightly slower
        const delay = Math.random() * 500;

        sourceLabel.transition()
          .delay(delay)
          .duration(500)
          .attr('opacity', 1)
          .transition()
          .delay(duration)
          .duration(500)
          .attr('opacity', 0)
          .remove();

        pathEl.transition()
          .delay(delay)
          .duration(duration)
          .ease(d3.easeCubicOut)
          .attr('stroke-dashoffset', 0)
          .on('end', () => {
            const impact = impactGroup.append('circle')
              .attr('cx', x2)
              .attr('cy', y2)
              .attr('r', 2)
              .attr('fill', color)
              .attr('filter', 'url(#glow)');

            impact.transition()
              .duration(800)
              .attr('r', 20)
              .attr('opacity', 0)
              .remove();

            pathEl.transition()
              .delay(1000)
              .duration(1000)
              .attr('opacity', 0)
              .remove();
            
            // Cleanup ref
            setTimeout(() => {
              animatedAttacksRef.current.delete(attack.id);
            }, 3000);
          });
      }
    });

  }, [worldData, attacks]);

  return (
    <div className="relative w-full h-full overflow-hidden rounded-2xl border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.5)] bg-[#0f172a]">
      <svg ref={svgRef} className="w-full h-full" />
      
      {/* Legend Overlay */}
      <div className="absolute bottom-6 left-6 flex flex-col gap-3 p-4 bg-black/40 backdrop-blur-md border border-white/5 rounded-xl">
        <div className="text-[10px] uppercase tracking-widest text-white/30 font-mono mb-1">威胁等级图例</div>
        <div className="flex items-center gap-3 text-[10px] font-mono text-white/60">
          <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
          <span>低/中危攻击</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono text-white/60">
          <div className="w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]" />
          <span>高危攻击</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono text-white/60">
          <div className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]" />
          <span>致命威胁</span>
        </div>
      </div>

      {/* Scanning Line Effect */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="w-full h-[2px] bg-blue-500/10 shadow-[0_0_15px_rgba(59,130,246,0.2)] animate-[scan_8s_linear_infinite]" />
      </div>

      <style>{`
        @keyframes scan {
          0% { transform: translateY(-100%); }
          100% { transform: translateY(1000%); }
        }
      `}</style>
    </div>
  );
};

export default WorldMap;
