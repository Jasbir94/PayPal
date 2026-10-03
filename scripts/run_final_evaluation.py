"""Run the Day 9 temporal, calibration, drift and illustrative cost reports."""
import json
import numpy as np
from pathlib import Path
from evaluation.temporal_evaluation import run as run_temporal
from evaluation.cost_analysis import run as run_costs
from evaluation.flagship_experiments import run as run_flagship


def main():
    temporal=run_temporal()
    costs=run_costs()
    flagship=run_flagship()
    day8=json.loads(Path('evaluation/day8_scenario_validation.json').read_text(encoding='utf-8'))
    phase_names=('passive_analysis_ms','full_analysis_ms','end_to_end_analysis_ms')
    latency={name:{'median_ms':float(np.median([case['latency_ms'][name] for case in day8['scenarios'] if name in case.get('latency_ms',{})])),
        'p95_ms':float(np.percentile([case['latency_ms'][name] for case in day8['scenarios'] if name in case.get('latency_ms',{})],95)),
        'samples':sum(name in case.get('latency_ms',{}) for case in day8['scenarios'])} for name in phase_names}
    component_names=sorted(set().union(*(set(row.get('component_latency_ms',{})) for row in flagship['cases'])))
    component_latency={name:{'median_ms':float(np.median([row['component_latency_ms'][name] for row in flagship['cases'] if name in row.get('component_latency_ms',{})])),
        'p95_ms':float(np.percentile([row['component_latency_ms'][name] for row in flagship['cases'] if name in row.get('component_latency_ms',{})],95)),
        'samples':sum(name in row.get('component_latency_ms',{}) for row in flagship['cases'])} for name in component_names}
    (Path('reports')/'latency_summary.json').write_text(json.dumps({'source':'13 Day 8 actual in-process simulator runs',
        'phase_latency':latency,'live_component_latency':component_latency,
        'component_source':'Five local in-process flagship simulator requests; tiny samples, indicative only.',
        'api_stress':json.loads(Path('evaluation/day7_api_stress.json').read_text(encoding='utf-8'))},indent=2),encoding='utf-8')
    temporal['outputs']=['final_model_comparison.csv','scenario_performance.csv',
        'hard_negative_performance.csv','calibration_report.json','drift_report.json',
        'threshold_analysis.csv','cost_analysis_config.json','flagship_experiments.json','latency_summary.json']
    with open('reports/final_evaluation.json','w',encoding='utf-8') as handle:
        json.dump(temporal,handle,indent=2,ensure_ascii=False)
    print(json.dumps({'split':temporal['split'],'models':temporal['models'],
        'threshold_rows':len(costs),'flagship_cases':len(flagship['cases'])},indent=2))


if __name__=='__main__':main()
