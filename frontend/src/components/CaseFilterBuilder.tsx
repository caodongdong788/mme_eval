import { useState } from "react";
import { AutoComplete, Button, InputNumber, Popover, Select } from "antd";
import { CloseOutlined, FilterOutlined, InfoCircleOutlined, PlusOutlined } from "@ant-design/icons";
import {
  CASE_FILTER_FIELDS,
  type CaseFilterField,
  type FilterCondition,
  type FilterFieldDefinition,
  type FilterValueOptions,
  defaultOperator,
  fieldDefinition,
  isActiveFilter,
  operatorNeedsValue,
  operatorsForField,
} from "../utils/caseFilters";

interface CaseFilterBuilderProps<Field extends string> {
  conditions: FilterCondition<Field>[];
  onChange: (conditions: FilterCondition<Field>[]) => void;
  valueOptions: FilterValueOptions<Field>;
  fields?: FilterFieldDefinition<Field>[];
  defaultField?: Field;
}

function newCondition<Field extends string>(
  fields: FilterFieldDefinition<Field>[],
  requestedDefault?: Field
): FilterCondition<Field> {
  const field =
    fields.find((item) => item.value === requestedDefault)?.value ??
    fields[0]?.value ??
    ("sub_scenario" as Field);
  return {
    id: `case-filter-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    field,
    operator: defaultOperator(field, fields),
    value: "",
  };
}

export function CaseFilterBuilder<Field extends string = CaseFilterField>({
  conditions,
  onChange,
  valueOptions,
  fields = CASE_FILTER_FIELDS as unknown as FilterFieldDefinition<Field>[],
  defaultField,
}: CaseFilterBuilderProps<Field>) {
  const [open, setOpen] = useState(false);
  const activeCount = conditions.filter(isActiveFilter).length;
  const fieldOptions = fields.map(({ value, label }) => ({ value, label }));

  const patchCondition = (id: string, patch: Partial<FilterCondition<Field>>) => {
    onChange(conditions.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const changeField = (condition: FilterCondition<Field>, field: Field) => {
    patchCondition(condition.id, {
      field,
      operator: defaultOperator(field, fields),
      value: undefined,
    });
  };

  const panel = (
    <div className="case-filter-panel">
      <div className="case-filter-panel__title">
        <span>
          设置筛选条件 <InfoCircleOutlined />
        </span>
        {activeCount > 0 && <span>{activeCount} 条已生效</span>}
      </div>
      <div className="case-filter-panel__conditions">
        {conditions.map((condition) => {
          const definition = fieldDefinition(condition.field, fields);
          const needsValue = operatorNeedsValue(condition.operator);
          return (
            <div className="case-filter-condition" key={condition.id}>
              <Select
                aria-label="筛选字段"
                value={condition.field}
                options={fieldOptions}
                onChange={(field) => changeField(condition, field)}
              />
              <Select
                aria-label="筛选运算符"
                value={condition.operator}
                options={operatorsForField(condition.field, fields)}
                onChange={(operator) =>
                  patchCondition(condition.id, {
                    operator,
                    value: operatorNeedsValue(operator) ? condition.value : undefined,
                  })
                }
              />
              {needsValue ? (
                definition.kind === "select" ? (
                  <Select
                    aria-label="筛选值"
                    value={condition.value}
                    placeholder="请选择"
                    options={definition.options}
                    onChange={(value) => patchCondition(condition.id, { value })}
                  />
                ) : definition.kind === "number" ? (
                  <InputNumber
                    aria-label="筛选值"
                    value={condition.value == null ? null : Number(condition.value)}
                    placeholder="请输入数值"
                    onChange={(value) =>
                      patchCondition(condition.id, { value: value == null ? undefined : String(value) })
                    }
                  />
                ) : (
                  <AutoComplete
                    aria-label="筛选值"
                    value={condition.value}
                    placeholder="请输入内容"
                    allowClear
                    options={valueOptions[condition.field]}
                    filterOption={(input, option) =>
                      String(option?.label ?? "")
                        .toLocaleLowerCase()
                        .includes(input.toLocaleLowerCase())
                    }
                    onChange={(value) => patchCondition(condition.id, { value })}
                  />
                )
              ) : (
                <div className="case-filter-condition__no-value">无需填写</div>
              )}
              <Button
                type="text"
                aria-label="删除筛选条件"
                icon={<CloseOutlined />}
                onClick={() => onChange(conditions.filter((item) => item.id !== condition.id))}
              />
            </div>
          );
        })}
        {conditions.length === 0 && (
          <div className="case-filter-panel__empty">暂无筛选条件</div>
        )}
      </div>
      <div className="case-filter-panel__footer">
        <Button
          type="link"
          icon={<PlusOutlined />}
          onClick={() => onChange([...conditions, newCondition(fields, defaultField)])}
        >
          添加筛选条件
        </Button>
        {conditions.length > 0 && (
          <Button type="link" onClick={() => onChange([])}>
            清空全部条件
          </Button>
        )}
      </div>
    </div>
  );

  return (
    <Popover
      content={panel}
      trigger="click"
      placement="bottomLeft"
      arrow={false}
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (nextOpen && conditions.length === 0) {
          onChange([newCondition(fields, defaultField)]);
        }
      }}
      overlayClassName="case-filter-popover"
    >
      <Button
        className={`case-filter-trigger${activeCount > 0 ? " is-active" : ""}`}
        type="default"
        icon={<FilterOutlined />}
      >
        筛选{activeCount > 0 ? <span className="case-filter-trigger__count">{activeCount}</span> : null}
      </Button>
    </Popover>
  );
}
