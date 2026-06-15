import { Col, Row } from "antd";
import { PairwiseConversationCol } from "./PairwiseConversationCol";
import { usePairwiseExpandedMessages } from "../hooks/usePairwiseExpandedMessages";

export function PairwiseExpandedRow({
  runAId,
  runBId,
  sampleId,
  runAName,
  runBName,
  comparisonId,
}: {
  runAId: number;
  runBId: number;
  sampleId: string;
  runAName: string;
  runBName: string;
  comparisonId: number;
}) {
  const { messagesA, messagesB } = usePairwiseExpandedMessages(runAId, runBId, sampleId);

  return (
    <Row gutter={12}>
      <Col span={12}>
        <PairwiseConversationCol
          messages={messagesA}
          runId={runAId}
          sampleId={sampleId}
          side="A"
          runName={runAName}
          comparisonId={comparisonId}
        />
      </Col>
      <Col span={12}>
        <PairwiseConversationCol
          messages={messagesB}
          runId={runBId}
          sampleId={sampleId}
          side="B"
          runName={runBName}
          comparisonId={comparisonId}
        />
      </Col>
    </Row>
  );
}
