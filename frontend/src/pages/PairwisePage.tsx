import { Space } from "antd";
import { useNavigate } from "react-router-dom";
import { PairwiseCreateCard } from "../components/PairwiseCreateCard";
import { PairwiseHistoryTable } from "../components/PairwiseHistoryTable";
import { usePairwisePage } from "../hooks/usePairwisePage";

export default function PairwisePage() {
  const navigate = useNavigate();
  const pw = usePairwisePage();

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <PairwiseCreateCard {...pw} />
      <PairwiseHistoryTable
        history={pw.history}
        onView={(id) => navigate(`/pairwise/${id}`)}
        onSaveNote={pw.saveNote}
        onDelete={pw.onDelete}
      />
    </Space>
  );
}
