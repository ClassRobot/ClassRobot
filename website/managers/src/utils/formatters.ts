import dayjs from "dayjs";


const roleLabelMap: Record<string, string> = {
  admin: "管理员",
  class_cadre: "班干部",
  student: "学生",
  teacher: "教师",
  user: "普通用户",
};


export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  return dayjs(value).format("YYYY-MM-DD HH:mm:ss");
}


export function formatRoleLabel(role: string): string {
  return roleLabelMap[role] ?? role;
}


export function formatYesNo(value: boolean): string {
  return value ? "是" : "否";
}
