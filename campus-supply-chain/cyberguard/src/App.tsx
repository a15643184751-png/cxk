import React, { useState, useEffect, useCallback } from 'react';
import WorldMap from './components/WorldMap';
import AttackLog from './components/AttackLog';
import Stats from './components/Stats';
import { AttackEvent } from './types';
import { generateRandomAttack } from './utils';
import { Shield, Activity, Lock, Cpu, Menu, Bell } from 'lucide-react';
import { motion } from 'motion/react';

// Target location (Changchun Vocational Institute of Technology)
const TARGET_LOCATION = { lat: 43.8170, lng: 125.3235 }; 

export default function App() {
  const [attacks, setAttacks] = useState<AttackEvent[]>([]);
  const [totalBlocked, setTotalBlocked] = useState(5200);
  const [activeThreats, setActiveThreats] = useState(0);
  const [uptime, setUptime] = useState('00:00:00');

  // Uptime counter
  useEffect(() => {
    // Start from 24:02:52
    const baseSeconds = (24 * 3600) + (2 * 60) + 52;
    const startTime = Date.now();
    
    const timer = setInterval(() => {
      const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
      const totalSeconds = baseSeconds + elapsedSeconds;
      
      const h = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
      const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
      const s = (totalSeconds % 60).toString().padStart(2, '0');
      setUptime(`${h}:${m}:${s}`);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const addAttackBatch = useCallback(() => {
    const r = Math.random();
    let batchSize = 0;
    if (r < 0.3) batchSize = Math.floor(Math.random() * 3) + 1; // 1-3 (30%)
    else if (r < 0.6) batchSize = Math.floor(Math.random() * 2) + 7; // 7-8 (30%)
    else batchSize = Math.floor(Math.random() * 3) + 4; // 4-6 (40%)

    for (let i = 0; i < batchSize; i++) {
      setTimeout(() => {
        setAttacks(prev => {
          if (prev.length >= 30) return prev;
          const newAttack = generateRandomAttack(TARGET_LOCATION.lat, TARGET_LOCATION.lng);
          return [newAttack, ...prev];
        });
        
        setTotalBlocked(prev => prev + Math.floor(Math.random() * 3) + 1);
        setActiveThreats(prev => Math.min(prev + 1, 100));
        
        setTimeout(() => {
          setActiveThreats(prev => Math.max(prev - 1, 0));
          setAttacks(prev => prev.slice(0, -1));
        }, 6000 + Math.random() * 4000);
      }, i * 400); // Staggered entry for better visual effect
    }
  }, []);

  // Simulation loop
  useEffect(() => {
    const runSimulation = () => {
      const nextInterval = 4000 + Math.random() * 6000;
      addAttackBatch();
      setTimeout(runSimulation, nextInterval);
    };
    
    const timeoutId = setTimeout(runSimulation, 1000);
    return () => clearTimeout(timeoutId);
  }, [addAttackBatch]);

  return (
    <div className="flex flex-col h-screen bg-[#050505] text-white font-sans overflow-hidden selection:bg-blue-500/30">
      {/* Top Header */}
      <header className="h-28 border-b border-white/10 flex items-center justify-between px-12 bg-[#0a0a0a]/95 backdrop-blur-2xl z-20 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_-20%,rgba(59,130,246,0.1),transparent)] pointer-events-none" />
        
        {/* Left: Logo */}
        <div className="flex items-center gap-6 relative z-10 w-1/4">
          <div className="w-14 h-14 bg-blue-500/10 rounded-2xl flex items-center justify-center border border-blue-500/20 shadow-[0_0_30px_rgba(59,130,246,0.15)] group">
            <Shield className="w-8 h-8 text-blue-500 group-hover:scale-110 transition-transform" />
          </div>
          <div className="hidden xl:flex flex-col">
            <span className="text-[10px] font-mono text-white/20 uppercase tracking-widest">系统版本</span>
            <span className="text-xs font-mono text-white/60 font-bold">V4.5.0 PRO</span>
          </div>
        </div>

        {/* Center: Large Title */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10 w-full max-w-3xl">
          <h1 
            className="text-6xl font-black tracking-[0.35em] text-white select-none drop-shadow-[0_0_20px_rgba(255,255,255,0.2)]"
            style={{ 
              fontFamily: "'Inter', sans-serif",
              background: "linear-gradient(to bottom, #ffffff 40%, #cbd5e1 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent"
            }}
          >
            安全态势感知
          </h1>
          <div className="flex items-center gap-6 mt-3 w-full justify-center">
            <div className="h-[1px] flex-1 bg-gradient-to-r from-transparent via-blue-500/40 to-transparent" />
            <p className="text-[12px] font-mono text-blue-400/50 uppercase tracking-[0.7em] whitespace-nowrap font-bold">SECURITY SITUATION AWARENESS SYSTEM</p>
            <div className="h-[1px] flex-1 bg-gradient-to-r from-transparent via-blue-500/40 to-transparent" />
          </div>
        </div>

        {/* Right: Stats & Controls */}
        <div className="flex items-center gap-12 relative z-10 w-1/4 justify-end">
          <div className="hidden lg:flex items-center gap-12 px-10 border-x border-white/5">
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-mono text-white/20 uppercase tracking-widest mb-1">实时吞吐量</span>
              <span className="text-sm font-mono text-white/80 font-bold tabular-nums">2.48 <span className="text-[10px] text-white/40">TB/s</span></span>
            </div>
          </div>
          
          <div className="flex items-center gap-5">
            <button className="p-3 rounded-2xl hover:bg-white/5 text-white/40 transition-all hover:text-white border border-transparent hover:border-white/10 active:scale-95">
              <Bell className="w-6 h-6" />
            </button>
            <button className="p-3 rounded-2xl hover:bg-white/5 text-white/40 transition-all hover:text-white border border-transparent hover:border-white/10 active:scale-95">
              <Menu className="w-6 h-6" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex overflow-hidden relative">
        {/* Dashboard Center */}
        <div className="flex-1 flex flex-col p-10 gap-10 overflow-hidden bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.04)_0%,transparent_70%)]">
          {/* Stats Row */}
          <Stats 
            totalBlocked={totalBlocked} 
            activeThreats={activeThreats} 
            uptime={uptime} 
          />

          {/* Map Section */}
          <div className="flex-1 relative min-h-0 group">
            <WorldMap attacks={attacks} />
            
            {/* Overlay Info - Repositioned to bottom-left to avoid blocking map */}
            <div className="absolute bottom-10 left-10 pointer-events-none">
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-[#0a0a0a]/90 backdrop-blur-3xl border border-blue-500/20 p-8 rounded-[2rem] shadow-[0_0_50px_rgba(0,0,0,0.6)] min-w-[360px]"
              >
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]" />
                    <h3 className="text-[11px] font-mono uppercase tracking-[0.5em] text-blue-400/80 font-bold">核心受保护节点</h3>
                  </div>
                  <div className="px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-[9px] font-mono text-blue-400">CVIT-HQ-01</div>
                </div>
                
                <div className="flex items-center gap-6 mb-8">
                  <div className="relative">
                    <div className="w-6 h-6 rounded-full bg-blue-500 shadow-[0_0_25px_rgba(59,130,246,0.8)] animate-pulse" />
                    <div className="absolute inset-0 w-6 h-6 rounded-full border border-blue-400 animate-ping opacity-20" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-2xl font-mono font-black text-white tracking-tighter leading-none">校园物资供应链安全中心</span>
                    <span className="text-[10px] font-mono text-white/20 mt-1 uppercase tracking-widest">Campus Supply Chain Security Center</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  <div className="bg-white/5 p-5 rounded-2xl border border-white/5 flex items-center justify-between">
                    <div>
                      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-1">网络标识 (IP Address)</div>
                      <div className="text-xl font-mono text-blue-400 font-black tracking-wider">202.198.16.1</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-1">物理位置</div>
                      <div className="text-sm font-mono text-white/80 font-bold">吉林 · 长春</div>
                    </div>
                  </div>
                  
                  <div className="bg-white/5 p-5 rounded-2xl border border-white/5 flex items-center justify-between">
                    <div>
                      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-1">地理坐标</div>
                      <div className="text-sm font-mono text-white/80 font-bold">{TARGET_LOCATION.lat}N / {TARGET_LOCATION.lng}E</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-[10px] font-mono text-emerald-500 font-bold uppercase tracking-widest">实时防护中</span>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>

            {/* Corner Accents */}
            <div className="absolute top-0 right-0 w-20 h-20 border-t-2 border-r-2 border-white/10 rounded-tr-3xl pointer-events-none" />
            <div className="absolute bottom-0 left-0 w-20 h-20 border-b-2 border-l-2 border-white/10 rounded-bl-3xl pointer-events-none" />
          </div>
        </div>

        {/* Right Sidebar - Attack Log */}
        <aside className="w-[420px] z-10 border-l border-white/5">
          <AttackLog attacks={attacks} />
        </aside>
      </main>

      {/* Bottom Status Bar */}
      <footer className="h-12 border-t border-white/10 bg-[#0a0a0a] px-12 flex items-center justify-between text-[10px] font-mono text-white/30 uppercase tracking-[0.25em] relative z-20">
        <div className="flex items-center gap-12">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
            <span className="text-emerald-500/80 font-bold">系统运行正常</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]" />
            <span className="text-amber-500/80 font-bold">风险等级: 中等</span>
          </div>
          <div className="h-4 w-[1px] bg-white/10" />
          <div className="flex items-center gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            <span>加密通道: AES-256-GCM</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
            <span>量子防护: ACTIVE</span>
          </div>
        </div>
        <div className="flex items-center gap-8">
          <span>© 2026 安全态势感知系统架构</span>
          <span className="text-blue-500/50 font-bold">SECURE CONNECTION ESTABLISHED</span>
        </div>
      </footer>
    </div>
  );
}

import { Globe } from 'lucide-react';
