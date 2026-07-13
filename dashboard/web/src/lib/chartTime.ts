/** K 線時間軸轉換。
 *
 *  日線:API 給 "YYYY-MM-DD",lightweight-charts 原生支援,原樣通過。
 *  分鐘級:API 給 UTC "YYYY-MM-DD HH:MM";圖表對數字 time 一律以 UTC 顯示,
 *  故轉 epoch 秒後平移 tzOffsetMin(getTimezoneOffset 語意:落後 UTC 的分鐘數,
 *  台北 = -480),讓顯示時間等於觀看者本地時間。
 */
export const toChartTime = (date: string, tzOffsetMin: number): string | number => {
  if (date.length <= 10) return date;
  const epochSec = new Date(date.replace(" ", "T") + ":00Z").getTime() / 1000;
  return epochSec - tzOffsetMin * 60;
};

/** 是否為分鐘/小時級序列(決定時間軸要不要顯示時刻)。 */
export const isIntraday = (dates: { date: string }[]): boolean =>
  dates.length > 0 && dates[0].date.length > 10;
