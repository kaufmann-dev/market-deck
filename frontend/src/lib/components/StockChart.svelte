<script lang="ts">
  import {
    CandlestickSeries,
    ColorType,
    createChart,
    HistogramSeries,
    LineSeries,
    type IChartApi,
    type Time,
  } from "lightweight-charts";
  import { onMount } from "svelte";
  import type { ChartResponse, OhlcPoint } from "../api/types";

  let {
    data,
    range,
    onRangeChange,
  }: { data: ChartResponse | null; range: string; onRangeChange: (range: string) => void } = $props();

  const ranges = [
    ["1M", "1mo"],
    ["3M", "3mo"],
    ["6M", "6mo"],
    ["1Y", "1y"],
    ["5Y", "5y"],
    ["Max", "max"],
  ];

  let chartEl: HTMLDivElement;
  let chart: IChartApi | null = null;
  let renderedSeries: any[] = [];
  let mode = $state<"line" | "candles">("candles");
  let showMa = $state(true);
  let showVolume = $state(true);

  function ma(points: OhlcPoint[], period: number) {
    const output = [];
    for (let index = period - 1; index < points.length; index += 1) {
      const slice = points.slice(index - period + 1, index + 1);
      const value = slice.reduce((sum, point) => sum + point.close, 0) / period;
      output.push({ time: points[index].date as Time, value });
    }
    return output;
  }

  function removeRenderedSeries() {
    if (!chart) return;
    for (const series of renderedSeries) chart.removeSeries(series);
    renderedSeries = [];
  }

  function render() {
    if (!chart) return;
    removeRenderedSeries();
    const points = data?.ohlc ?? [];
    if (!points.length) return;

    if (mode === "candles") {
      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#68d391",
        downColor: "#fc8181",
        wickUpColor: "#68d391",
        wickDownColor: "#fc8181",
        borderVisible: false,
      });
      candleSeries.setData(
        points.map((point) => ({
          time: point.date as Time,
          open: point.open ?? point.close,
          high: point.high ?? point.close,
          low: point.low ?? point.close,
          close: point.close,
        })),
      );
      renderedSeries.push(candleSeries);
    } else {
      const lineSeries = chart.addSeries(LineSeries, { color: "#ffffff", lineWidth: 2 });
      lineSeries.setData(points.map((point) => ({ time: point.date as Time, value: point.close })));
      renderedSeries.push(lineSeries);
    }

    if (showMa) {
      const ma20 = chart.addSeries(LineSeries, { color: "#a0a0a0", lineWidth: 1 });
      ma20.setData(ma(points, 20));
      const ma50 = chart.addSeries(LineSeries, { color: "#ffffff", lineWidth: 1 });
      ma50.setData(ma(points, 50));
      renderedSeries.push(ma20, ma50);
    }

    if (showVolume) {
      const volume = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "",
      });
      volume.priceScale().applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
      volume.setData(
        points.map((point, index) => {
          const previous = points[index - 1]?.close ?? point.close;
          return {
            time: point.date as Time,
            value: point.volume ?? 0,
            color: point.close >= previous ? "rgba(104, 211, 145, 0.35)" : "rgba(252, 129, 129, 0.35)",
          };
        }),
      );
      renderedSeries.push(volume);
    }

    chart.timeScale().fitContent();
  }

  onMount(() => {
    chart = createChart(chartEl, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a0a0a0",
      },
      grid: {
        vertLines: { color: "#222222" },
        horzLines: { color: "#222222" },
      },
      rightPriceScale: { borderColor: "#333333" },
      timeScale: { borderColor: "#333333", rightOffset: 8, barSpacing: 6 },
      crosshair: { mode: 1 },
    });
    render();
    return () => {
      chart?.remove();
      chart = null;
      renderedSeries = [];
    };
  });

  $effect(() => {
    data;
    mode;
    showMa;
    showVolume;
    render();
  });
</script>

<div class="stock-chart-panel">
  <div class="chart-toolbar">
    <div class="btn-group">
      {#each ranges as [label, value] (value)}
        <button class={range === value ? "a-blue" : ""} onclick={() => onRangeChange(value)}>
          {label}
        </button>
      {/each}
    </div>
    <div class="btn-group">
      <button class={mode === "candles" ? "a-purple" : ""} onclick={() => (mode = "candles")}>
        Candles
      </button>
      <button class={mode === "line" ? "a-purple" : ""} onclick={() => (mode = "line")}>
        Line
      </button>
      <button class={showMa ? "a-purple" : ""} onclick={() => (showMa = !showMa)}>
        MA
      </button>
      <button class={showVolume ? "a-purple" : ""} onclick={() => (showVolume = !showVolume)}>
        Volume
      </button>
    </div>
  </div>
  <div class="chart-canvas" bind:this={chartEl}></div>
</div>
