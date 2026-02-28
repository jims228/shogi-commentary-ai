export type LessonStatus = "locked" | "available" | "completed";
export type LessonCategory = "basics" | "piece-move" | "tsume-1" | "tsume-2" | "tsume-3";

export interface Lesson {
  id: string;
  title: string;
  description: string;
  category: LessonCategory;
  status: LessonStatus;
  href?: string;
  stars?: number; // 0-3
  order: number;
  prerequisites?: string[];
}
