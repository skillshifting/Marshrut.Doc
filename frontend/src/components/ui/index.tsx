import * as React from 'react';
import * as TabsPrimitive from '@radix-ui/react-tabs';
import {cva, type VariantProps} from 'class-variance-authority';
import {clsx, type ClassValue} from 'clsx';
import {twMerge} from 'tailwind-merge';
export const cn=(...args:ClassValue[])=>twMerge(clsx(args));
const buttonStyles=cva('inline-flex items-center justify-center gap-2 rounded-sm border text-[13px] font-semibold tracking-[.01em] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50 disabled:pointer-events-none', {variants:{variant:{default:'border-accent bg-accent text-white hover:bg-[#193c52]',outline:'border-line bg-white text-ink hover:border-accent hover:bg-slate-50',ghost:'border-transparent text-accent hover:bg-slate-100',danger:'border-red-700 bg-red-700 text-white hover:bg-red-800'},size:{default:'h-9 px-3',sm:'h-8 px-3',lg:'h-10 px-4'}},defaultVariants:{variant:'default',size:'default'}});
export function Button({className,variant,size,...props}:React.ButtonHTMLAttributes<HTMLButtonElement>&VariantProps<typeof buttonStyles>){return <button className={cn(buttonStyles({variant,size}),className)} {...props}/>}
export function Card({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div className={cn('rounded-sm border border-line bg-white',className)} {...props}/>}
export function CardHeader({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div className={cn('px-4 pt-4 pb-2',className)} {...props}/>}
export function CardContent({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div className={cn('px-4 pb-4',className)} {...props}/>}
export function Input(props:React.InputHTMLAttributes<HTMLInputElement>){return <input {...props} className={cn('h-9 w-full rounded-sm border border-line bg-white px-2.5 text-[13px] outline-none focus:ring-1 focus:ring-accent focus:border-accent',props.className)}/>}
export function Textarea(props:React.TextareaHTMLAttributes<HTMLTextAreaElement>){return <textarea {...props} className={cn('w-full rounded-sm border border-line bg-white px-2.5 py-2 text-[13px] outline-none focus:ring-1 focus:ring-accent focus:border-accent',props.className)}/>}
export function Badge({children,tone='neutral'}:{children:React.ReactNode,tone?:'neutral'|'amber'|'green'|'red'}){return <span className={cn('inline-flex items-center rounded-sm border bg-transparent px-1.5 py-0.5 font-mono text-[10px] font-medium leading-4 tracking-[.01em]',tone==='amber'?'border-amber-300 text-amber-800':tone==='green'?'border-emerald-300 text-emerald-800':tone==='red'?'border-red-300 text-red-800':'border-slate-300 text-slate-600')}>{children}</span>}
export const Tabs=TabsPrimitive.Root; export const TabsList=TabsPrimitive.List; export const TabsTrigger=TabsPrimitive.Trigger; export const TabsContent=TabsPrimitive.Content;
