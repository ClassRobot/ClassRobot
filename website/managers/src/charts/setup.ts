import { use } from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from "echarts/components";


use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, LegendComponent, TitleComponent, TooltipComponent]);
