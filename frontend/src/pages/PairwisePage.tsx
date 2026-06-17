import { DashboardPageShell } from "../components/DashboardPageShell";
import { PairwiseCreateCard } from "../components/PairwiseCreateCard";
import { PairwiseHistoryTable } from "../components/PairwiseHistoryTable";
import { usePairwisePage } from "../hooks/usePairwisePage";

export default function PairwisePage() {
  const pw = usePairwisePage();

  return (
    <DashboardPageShell
      title="Pairwise 对比"
      sub="同一裁判逐题 PK 两次评测，快速判断版本优劣"
    >
      <PairwiseCreateCard {...pw} />
      <PairwiseHistoryTable
        history={pw.history}
        onSaveNote={pw.saveNote}
        onDelete={pw.onDelete}
      />
    </DashboardPageShell>
  );
}
