{#
  커스텀 generate_schema_name: target schema 접두어를 붙이지 않는다.

  dbt 기본 동작은 custom schema가 지정되면 `<target.schema>_<custom_schema>`
  형태로 접두어를 붙인다. 이 프로젝트는 메달리온 레이어를 스키마 접두어가 아니라
  tag(dbt)/kind(Dagster)로 표기하고, 모델을 Iceberg 네임스페이스(eicu·mimiciv)에
  그대로 적재하므로 custom schema를 접두어 없이 그대로 사용한다.

  - custom schema 미지정: target.schema(dev/prod) 사용
  - custom schema 지정: 그 값을 그대로 사용

  ref: dbt — Custom schemas / generate_schema_name
       https://docs.getdbt.com/docs/build/custom-schemas
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
