import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import random
import time
from datetime import datetime
import json

# 初始化Dash应用
app = dash.Dash(__name__)

# 模拟LOG数据
def generate_log_data():
    log_types = ['INFO', 'WARNING', 'ERROR', 'DEBUG']
    log_contents = [
        'User authentication successful',
        'Database connection established',
        'Cache miss for key: user_123',
        'API request processed in 45ms',
        'Memory usage at 78%',
        'Failed to connect to external service',
        'Backup completed successfully',
        'Security scan completed - no threats found'
    ]
    
    return {
        'type': random.choice(log_types),
        'content': random.choice(log_contents),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

# 模拟集群动态数据
def generate_cluster_data():
    nodes = ['node-1', 'node-2', 'node-3', 'node-4']
    statuses = ['Running', 'Pending', 'Failed', 'Terminating']
    
    cluster_data = []
    for node in nodes:
        cluster_data.append({
            'node': node,
            'status': random.choice(statuses),
            'cpu_usage': random.randint(20, 95),
            'memory_usage': random.randint(30, 90),
            'pods': random.randint(5, 25)
        })
    
    return cluster_data

# 应用布局
app.layout = html.Div([
    # 主容器
    html.Div([
        # LOG显示区域 (左侧70%)
        html.Div([
            html.H3("系统日志", style={
                'color': '#2c3e50',
                'margin-bottom': '20px',
                'font-weight': 'bold'
            }),
            html.Div(id='log-display', style={
                'background-color': '#f8f9fa',
                'border': '2px solid #e9ecef',
                'border-radius': '15px',
                'padding': '20px',
                'min-height': '200px',
                'font-family': 'monospace'
            })
        ], style={
            'width': '70%',
            'float': 'left',
            'padding': '20px',
            'box-sizing': 'border-box'
        }),
        
        # 集群动态区域 (右侧30%)
        html.Div([
            html.H3("集群动态", style={
                'color': '#2c3e50',
                'margin-bottom': '20px',
                'font-weight': 'bold'
            }),
            html.Div(id='cluster-display', style={
                'background-color': '#f8f9fa',
                'border': '2px solid #e9ecef',
                'border-radius': '15px',
                'padding': '20px',
                'min-height': '200px'
            })
        ], style={
            'width': '30%',
            'float': 'right',
            'padding': '20px',
            'box-sizing': 'border-box'
        })
    ], style={
        'width': '100%',
        'overflow': 'hidden',
        'margin-bottom': '50px'
    }),
    
    # 页脚留白区域
    html.Div([
        html.P("© 2024 SRE Arena Dashboard", style={
            'text-align': 'center',
            'color': '#6c757d',
            'margin': '0',
            'padding': '20px'
        })
    ], style={
        'background-color': '#f8f9fa',
        'border-top': '1px solid #e9ecef',
        'margin-top': '50px',
        'min-height': '80px',
        'display': 'flex',
        'align-items': 'center',
        'justify-content': 'center'
    }),
    
    # 定时器组件
    dcc.Interval(
        id='interval-component',
        interval=3*1000,  # 3秒更新一次
        n_intervals=0
    )
], style={
    'font-family': 'Arial, sans-serif',
    'margin': '0',
    'padding': '20px',
    'background-color': '#ffffff',
    'min-height': '100vh'
})

# LOG显示回调
@app.callback(
    Output('log-display', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_log_display(n):
    log_data = generate_log_data()
    
    # 根据日志类型设置颜色
    type_colors = {
        'INFO': '#28a745',
        'WARNING': '#ffc107',
        'ERROR': '#dc3545',
        'DEBUG': '#17a2b8'
    }
    
    return html.Div([
        html.Div([
            html.Span(f"[{log_data['timestamp']}] ", style={'color': '#6c757d'}),
            html.Span(log_data['type'], style={
                'color': type_colors.get(log_data['type'], '#000'),
                'font-weight': 'bold',
                'background-color': type_colors.get(log_data['type'], '#000') + '20',
                'padding': '2px 8px',
                'border-radius': '4px',
                'margin-right': '10px'
            }),
            html.Span(log_data['content'], style={'color': '#2c3e50'})
        ], style={'margin-bottom': '15px'}),
        
        # 添加一些历史日志示例
        html.Div([
            html.Span("[2024-01-15 14:30:25] ", style={'color': '#6c757d'}),
            html.Span("INFO", style={
                'color': '#28a745',
                'font-weight': 'bold',
                'background-color': '#28a74520',
                'padding': '2px 8px',
                'border-radius': '4px',
                'margin-right': '10px'
            }),
            html.Span("Database connection pool initialized", style={'color': '#2c3e50'})
        ], style={'margin-bottom': '10px', 'opacity': '0.7'}),
        
        html.Div([
            html.Span("[2024-01-15 14:30:20] ", style={'color': '#6c757d'}),
            html.Span("WARNING", style={
                'color': '#ffc107',
                'font-weight': 'bold',
                'background-color': '#ffc10720',
                'padding': '2px 8px',
                'border-radius': '4px',
                'margin-right': '10px'
            }),
            html.Span("High memory usage detected on node-2", style={'color': '#2c3e50'})
        ], style={'margin-bottom': '10px', 'opacity': '0.7'}),
        
        html.Div([
            html.Span("[2024-01-15 14:30:15] ", style={'color': '#6c757d'}),
            html.Span("ERROR", style={
                'color': '#dc3545',
                'font-weight': 'bold',
                'background-color': '#dc354520',
                'padding': '2px 8px',
                'border-radius': '4px',
                'margin-right': '10px'
            }),
            html.Span("Failed to connect to Redis cluster", style={'color': '#2c3e50'})
        ], style={'opacity': '0.7'})
    ])

# 集群动态显示回调
@app.callback(
    Output('cluster-display', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_cluster_display(n):
    cluster_data = generate_cluster_data()
    
    # 状态颜色映射
    status_colors = {
        'Running': '#28a745',
        'Pending': '#ffc107',
        'Failed': '#dc3545',
        'Terminating': '#6c757d'
    }
    
    cluster_items = []
    for node in cluster_data:
        cluster_items.append(
            html.Div([
                html.Div([
                    html.Strong(node['node'], style={'color': '#2c3e50'}),
                    html.Span(node['status'], style={
                        'color': status_colors.get(node['status'], '#000'),
                        'font-weight': 'bold',
                        'background-color': status_colors.get(node['status'], '#000') + '20',
                        'padding': '2px 6px',
                        'border-radius': '3px',
                        'margin-left': '10px',
                        'font-size': '12px'
                    })
                ], style={'margin-bottom': '8px'}),
                
                html.Div([
                    html.Span(f"CPU: {node['cpu_usage']}%", style={'font-size': '12px', 'color': '#6c757d'}),
                    html.Br(),
                    html.Span(f"Memory: {node['memory_usage']}%", style={'font-size': '12px', 'color': '#6c757d'}),
                    html.Br(),
                    html.Span(f"Pods: {node['pods']}", style={'font-size': '12px', 'color': '#6c757d'})
                ], style={'margin-left': '10px', 'margin-bottom': '15px'})
            ], style={
                'border-bottom': '1px solid #e9ecef',
                'padding-bottom': '10px'
            })
        )
    
    return cluster_items

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)

