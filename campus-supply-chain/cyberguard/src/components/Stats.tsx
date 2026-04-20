import React from 'react';
import { ShieldCheck, Zap, Globe, Clock } from 'lucide-react';
import { cn } from '../utils';

interface StatsProps {
  totalBlocked: number;
  activeThreats: number;
  uptime: string;
}

const Stats: React.FC<StatsProps> = ({ totalBlocked, activeThreats, uptime }) => {
  const stats = [
    { label: '累计拦截攻击', value: totalBlocked.toLocaleString(), icon: ShieldCheck, color: 'text-emerald-500', glow: 'shadow-emerald-500/20' },
    { label: '当前活跃威胁', value: activeThreats, icon: Zap, color: 'text-amber-500', glow: 'shadow-amber-500/20' },
    { label: '系统运行时间', value: uptime, icon: Clock, color: 'text-blue-500', glow: 'shadow-blue-500/20' },
    { label: '全球防护节点', value: '24', icon: Globe, color: 'text-purple-500', glow: 'shadow-purple-500/20' },
  ];

  return (
    <div className="grid grid-cols-4 gap-4">
      {stats.map((stat, i) => (
        <div key={i} className="bg-[#0a0a0a] border border-white/5 p-5 rounded-2xl flex items-center gap-5 relative overflow-hidden group hover:border-white/10 transition-all">
          <div className="absolute top-0 right-0 w-24 h-24 bg-white/5 rounded-full -mr-12 -mt-12 group-hover:bg-white/10 transition-colors" />
          <div className={cn(
            "p-3.5 rounded-xl bg-white/5 shadow-lg",
            stat.color,
            stat.glow
          )}>
            <stat.icon className="w-6 h-6" />
          </div>
          <div className="relative z-10">
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/30 mb-1.5">{stat.label}</p>
            <p className="text-2xl font-mono font-bold text-white/90 tracking-tighter">{stat.value}</p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default Stats;
