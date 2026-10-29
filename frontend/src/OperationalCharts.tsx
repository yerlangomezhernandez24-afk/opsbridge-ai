import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export interface NamedValue { name: string; value: number }
export interface DailyValue { date: string; total: number }

export function StatusBarChart({ data }: { data: NamedValue[] }) {
  return <ResponsiveContainer width="100%" height="100%"><BarChart data={data}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} width={26} /><Tooltip /><Bar dataKey="value" fill="#6757f5" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer>
}

export function PriorityPieChart({ data }: { data: NamedValue[] }) {
  const colors = ['#ff8b78', '#f0a54a', '#46b8f5', '#13b8a6']
  return <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72}>{colors.map(color => <Cell key={color} fill={color} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer>
}

export function DailyVolumeChart({ data }: { data: DailyValue[] }) {
  return <ResponsiveContainer width="100%" height="100%"><BarChart data={data}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="total" fill="#13b8a6" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer>
}
