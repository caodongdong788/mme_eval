import { http } from "./client";
import type {
  Benchmark,
  BenchmarkCaseYaml,
  CaseBrief,
  DeriveBenchmarkYamlPayload,
  OverwriteBenchmarkYamlPayload,
} from "./types";

export const selectableBenchmarks = (list: Benchmark[]): Benchmark[] =>
  list.filter((b) => b.source !== "builtin");

export const benchmarksApi = {
  listBenchmarks: () => http.get<Benchmark[]>("/benchmarks").then((r) => r.data),
  getBenchmarkCases: (id: number) =>
    http.get<CaseBrief[]>(`/benchmarks/${id}/cases`).then((r) => r.data),
  getBenchmarkCaseYaml: (benchmarkId: number, sampleId: string) =>
    http
      .get<BenchmarkCaseYaml>(`/benchmarks/${benchmarkId}/cases/${sampleId}/yaml`)
      .then((r) => r.data),
  saveBenchmarkCaseYaml: (benchmarkId: number, sampleId: string, yaml_text: string) =>
    http
      .put<BenchmarkCaseYaml>(`/benchmarks/${benchmarkId}/cases/${sampleId}/yaml`, {
        yaml_text,
      })
      .then((r) => r.data),
  uploadBenchmark: (form: FormData) =>
    http.post<Benchmark>("/benchmarks", form).then((r) => r.data),
  replaceBenchmark: (id: number, form: FormData) =>
    http.put<Benchmark>(`/benchmarks/${id}`, form).then((r) => r.data),
  updateBenchmark: (id: number, payload: { name?: string; description?: string }) =>
    http.patch<Benchmark>(`/benchmarks/${id}`, payload).then((r) => r.data),
  downloadBenchmarkUrl: (id: number) => `/api/benchmarks/${id}/download`,
  deleteBenchmark: (id: number) => http.delete(`/benchmarks/${id}`),
  deriveBenchmarkFromYaml: (id: number, payload: DeriveBenchmarkYamlPayload) =>
    http.post<Benchmark>(`/benchmarks/${id}/derive-yaml`, payload).then((r) => r.data),
  overwriteBenchmarkFromYaml: (id: number, payload: OverwriteBenchmarkYamlPayload) =>
    http.post<Benchmark>(`/benchmarks/${id}/overwrite-yaml`, payload).then((r) => r.data),
};
