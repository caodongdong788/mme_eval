import { Alert, Result, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import PairwiseCalibrateModal from "../components/PairwiseCalibrateModal";
import { PairwiseCaseTable } from "../components/PairwiseCaseTable";
import { PairwiseDetailRunningCard } from "../components/PairwiseDetailRunningCard";
import { PairwiseDetailSummaryCard } from "../components/PairwiseDetailSummaryCard";
import { usePairwiseDetail } from "../hooks/usePairwiseDetail";

export default function PairwiseDetailPage() {
  const { comparisonId } = useParams();
  const id = Number(comparisonId);
  const pw = usePairwiseDetail(id);

  if (!pw.detail) {
    return pw.detailError ? (
      <div className="dash-page">
        <Result
          status="warning"
          title="无法加载对比详情"
          subTitle={pw.detailError}
          extra={
            <Link to="/pairwise" className="dash-table__link">
              返回 Pairwise 列表
            </Link>
          }
        />
      </div>
    ) : (
      <div className="dash-page" style={{ display: "grid", placeItems: "center", paddingTop: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  const detail = pw.detail;

  return (
    <div className="dash-page">
      {detail.status === "running" && (
        <PairwiseDetailRunningCard
          detail={detail}
          runAName={pw.runAName}
          runBName={pw.runBName}
          doneCases={pw.doneCases}
          totalCases={pw.totalCases}
          pct={pw.pct}
        />
      )}
      {detail.status === "failed" && (
        <Alert type="error" showIcon message="对比失败" description={detail.error_msg} />
      )}

      {detail.status === "done" && (
        <>
          <PairwiseDetailSummaryCard
            detail={detail}
            conclusion={pw.conclusion}
            runAName={pw.runAName}
            runBName={pw.runBName}
            aWins={pw.aWins}
            bWins={pw.bWins}
            ties={pw.ties}
            total={pw.total}
            orderSensitiveN={pw.orderSensitiveN}
            safetyDoubtN={pw.safetyDoubtN}
            humanCalibratedN={pw.humanCalibratedN}
            byDim={pw.byDim}
            diffKeys={pw.diffKeys}
          />
          <PairwiseCaseTable
            comparisonId={id}
            detail={detail}
            filtered={pw.filtered}
            conclusionFilter={pw.conclusionFilter}
            setConclusionFilter={pw.setConclusionFilter}
            confidenceFilter={pw.confidenceFilter}
            setConfidenceFilter={pw.setConfidenceFilter}
            hasActiveFilters={pw.hasActiveFilters}
            resetFilters={pw.resetFilters}
            tablePage={pw.tablePage}
            setTablePage={pw.setTablePage}
            expandedKeys={pw.expandedKeys}
            setExpandedKeys={pw.setExpandedKeys}
            setCalibrateVerdict={pw.setCalibrateVerdict}
            runAName={pw.runAName}
            runBName={pw.runBName}
          />
        </>
      )}

      <PairwiseCalibrateModal
        open={pw.calibrateVerdict != null}
        comparisonId={id}
        verdict={pw.calibrateVerdict}
        onClose={() => pw.setCalibrateVerdict(null)}
        onSaved={pw.load}
      />
    </div>
  );
}
