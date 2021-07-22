import dash
import dash_core_components as dcc
import dash_html_components as html
import matplotlib.pyplot as plt
from matplotlib import animation
import dash_table
import numpy as np
import pandas as pd
import sys
import requests
from bs4 import BeautifulSoup
import time
from urllib.request import urlopen
import plotly.graph_objs as go
import datetime
import gunicorn
from whitenoise import WhiteNoise

app = dash.Dash(__name__, external_stylesheets = ['/assets/style_sheet.css'])
server = app.server
server.wsgi_app = WhiteNoise(server.wsgi_app, root = 'static/')

league_size = 12

url = 'https://www.fantasypros.com/nfl/adp/ppr-overall.php'
ff_html = urlopen(url)
soup = BeautifulSoup(ff_html, features="lxml")
rows = soup.findAll('tr')
team_stats = [[td.getText() for td in rows[i].findAll('td')] for i in range(len(rows))]
team_stats = pd.DataFrame(team_stats)[1:].reset_index(drop=True)
team_stats['UID'] = team_stats[1].str.replace(' \(.+','')
team_stats['UID'] = team_stats['UID'].fillna('Missing')
team_stats['UID'] = team_stats['UID'].str.replace('III ', '')
team_stats['UID'] = team_stats['UID'].str.replace('II ', '')
team_stats['UID'] = team_stats['UID'].str.replace('Jr. ', '')
team_stats['UID'] = team_stats['UID'].str.replace('Sr. ', '')
team_stats['UID'] = team_stats['UID'].str.replace('V ', '')
team_stats['UID'] = team_stats['UID'].str.replace('IV ', '')
adp_dict = dict(zip(team_stats['UID'], team_stats.index + 1))


all_df = pd.DataFrame()

for pos in ['QB', 'RB', 'WR', 'TE']:
    url = 'https://www.fantasypros.com/nfl/projections/'+pos.lower()+'.php?week=draft&scoring=PPR&week=draft'
    ff_html = urlopen(url)
    soup = BeautifulSoup(ff_html, features="lxml")
    rows = soup.findAll('tr')
    projections = [[td.getText() for td in rows[i].findAll('td')] for i in range(len(rows))]
    projections = pd.DataFrame(projections)[2:].reset_index(drop=True)
    if pos == 'RB' or pos == 'WR':
        projections.columns = ['Name', 'Rushes', 'Rush Yards', 'Rush TDs', 'Receptions', 'Rec Yards', 'Rec TDs', 'Fumbles', 'PPG PROJECTION']
        projections = projections[projections['Receptions'].notna()]
        projections['rush_bonus'] = ((projections['Rush Yards'].str.replace(',', '').astype(float) / 17) * .015) * 17
        projections['rec_bonus'] = ((projections['Rec Yards'].str.replace(',', '').astype(float) / 17) * .015) * 17
        projections['PPG PROJECTION'] = (projections['PPG PROJECTION'].astype(float) + projections['rush_bonus'].astype(float) + projections['rec_bonus'].astype(float)  + projections['Fumbles'].astype(float)) / 17
    elif pos == 'QB':
        projections.columns = ['Name', 'PA', 'PC', 'Pass Yards', 'Pass TDs', 'Pass INTs', 'Rushes', 'Rush Yards', 'Rush TDs', 'Fumbles', 'PPG PROJECTION']
        projections = projections[projections['Rushes'].notna()].copy()
        projections['rush_bonus'] = ((projections['Rush Yards'].str.replace(',', '').astype(float) / 17) * .015) * 17
        projections['pass_bonus'] = ((projections['Pass Yards'].str.replace(',', '').astype(float) / 17) * .005) * 17
        projections['PPG PROJECTION'] = (projections['PPG PROJECTION'].astype(float) + projections['rush_bonus'].astype(float) + projections['pass_bonus'].astype(float) + projections['Fumbles'].astype(float) + projections['Pass INTs'].astype(float)) / 17
    elif pos == 'TE':
        projections.columns = ['Name', 'Receptions', 'Rec Yards', 'Rec TDs', 'Fumbles', 'PPG PROJECTION']
        projections = projections[projections['Fumbles'].notna()].copy()
        projections['rec_bonus'] = ((projections['Rec Yards'].str.replace(',', '').astype(float) / 17) * .015) * 17
        projections['PPG PROJECTION'] = (projections['PPG PROJECTION'].astype(float) + projections['rec_bonus'].astype(float) + projections['Fumbles'].astype(float)) / 17
    projections['Team'] = projections['Name'].str.split(' ').str[-2]
    projections['Name'] = projections['Name'].str.strip().str[:-3].str.strip()
    if pos == 'RB':
        projections['Position'] = 'HB'
    else:
        projections['Position'] = pos
    projections = projections[['Name', 'Team', 'Position', 'PPG PROJECTION']]
    all_df = all_df.append(projections)

all_df['TEAM ABBREV'] = all_df['Team'].copy()
all_df['UID'] = all_df['Name'] + ' ' + all_df['TEAM ABBREV']
all_df['UID'] = all_df['UID'].str.replace('III ', '')
all_df['UID'] = all_df['UID'].str.replace('II ', '')
all_df['UID'] = all_df['UID'].str.replace('Jr. ', '')
all_df['UID'] = all_df['UID'].str.replace('Sr. ', '')
all_df['UID'] = all_df['UID'].str.replace('V ', '')
all_df['UID'] = all_df['UID'].str.replace('IV ', '')
all_df['ADP'] = all_df['UID'].map(adp_dict)
all_df['ADP'] = all_df['ADP'].fillna(400)


df = all_df[['Name', 'Team', 'Position', 'PPG PROJECTION']]
df['PPG PROJECTION'] = df['PPG PROJECTION'].round(2)
df = df.sort_values(by='PPG PROJECTION', ascending=False).reset_index(drop=True)
df['PPG PROJECTION'] = df['PPG PROJECTION'].astype(float)
df = df[df['PPG PROJECTION'] > 1]
teams_list = df['Team'].unique().tolist()
position_list = ['ALL', 'QB', 'HB', 'WR', 'TE', 'FLEX']
## Calculate Value at each postion above hardcoded avg. points / game of replacement player
df.loc[df['Position'] == 'QB', 'PPG+'] = df.loc[df['Position'] == 'QB', 'PPG PROJECTION'] - 16.34
df.loc[df['Position'] == 'HB', 'PPG+'] = df.loc[df['Position'] == 'HB', 'PPG PROJECTION'] - 12.43
df.loc[df['Position'] == 'WR', 'PPG+'] = df.loc[df['Position'] == 'WR', 'PPG PROJECTION'] - 11.96
df.loc[df['Position'] == 'TE', 'PPG+'] = df.loc[df['Position'] == 'TE', 'PPG PROJECTION'] - 8.69
adp_df = all_df.sort_values(by = 'ADP')
adp_df['ADP'] = adp_df['ADP']
adp_df = adp_df[['ADP', 'Name', 'Position', 'Team']]
adp_mapper = dict(zip(adp_df['Name'], adp_df['ADP']))
df['ADP'] = df['Name'].map(adp_mapper)
df['ADP'] = df['ADP']/league_size
df['ADP'] =df['ADP'].round(2)
df['Text'] = df['PPG PROJECTION'].round(1).astype(str) + ' - ' + df['Name'] + ' (' + df['ADP'].round(1).astype(str) + ')'

teams_list = sorted(df['Team'].unique().tolist())
teams_list.insert(0, 'ALL TEAMS')

roster_df = pd.DataFrame()
roster_list = ['-','-','-',
              '-','-','-','-','-','-','-',
              '-','-','-','-','-','-','-','-','-','-', '-', '-', '-',
              '-','-','-']
roster_df['Pos.'] = ['QB1', 'QB2', 'QB3',
                     'RB1', 'RB2', 'RB3', 'RB4', 'RB5', 'RB6', 'RB7',
                     'WR1', 'WR2', 'WR3', 'WR4', 'WR5', 'WR6', 'WR7', 'WR8', 'WR9', 'WR10', 'WR11', 'WR12', 'WR13',
                     'TE1', 'TE2', 'TE3']
roster_df['Name'] = roster_list

adp_df = adp_df.sort_values(by='ADP', ascending = True).reset_index(drop=True)
roster_mapper = adp_df['Name'].tolist()
roster_mapper_pos = adp_df['Position'].tolist()
team_pos_count = {}

data_stores = {}
data_stores['roster_list'] = roster_list
data_stores['adp_df'] = adp_df.values
data_stores['adp_df_columns'] = adp_df.columns
data_stores['roster_df'] = roster_df.values
data_stores['roster_df_columns'] = roster_df.columns
data_stores['df'] = df.values
data_stores['df_columns'] = df.columns
data_stores['stacking_dict'] = team_pos_count

colors = {
    'background': '#ffffff',
    'text': 'dimgrey'
}
app.layout = html.Div(style={'backgroundColor': colors['background']}, children=[
    html.H1(
        children='Best Ball Draft Dashboard',
        style={
            'textAlign': 'center',
            'color': colors['text']
        }
    ),
    html.Div([
        dcc.Dropdown(
            id='position-dropdown',
            options=[{'label': i, 'value': i} for i in position_list],
            value='ALL'),
             ], style={'width': '10%', 'marginLeft': '20px', 'display': 'inline-block'}
    ),
    html.Div([
        dcc.Dropdown(
            id='value-dropdown',
            options=[{'label': i, 'value': i} for i in ['POINTS PER GAME', 'POSITIONAL VALUE (PPG+)']],
            value='POINTS PER GAME'),
             ], style={'width': '20%', 'marginLeft': '40px', 'display': 'inline-block'}
    ),
    html.Div([
        dcc.Dropdown(
            id='team-dropdown',
            options=[{'label': i, 'value': i} for i in teams_list],
            value='ALL TEAMS'),
             ], style={'width': '15%', 'marginLeft': '40px', 'display': 'inline-block'}
    ),
    html.Div([
        dcc.Dropdown(
            id='size-dropdown',
            options=[{'label': i, 'value': i} for i in [15, 20, 25, 30, 50]],
            value=15),
             ], style={'width': '7%', 'marginLeft': '40px', 'display': 'inline-block'}
    ),
    html.Button('Delete', id = 'delete-button', n_clicks_timestamp = 0, style={'marginLeft': '85px', 'marginBottom': '10px', 'width': '10%', 'display': 'inline-block', 'color': 'white', 'backgroundColor': 'red'}),
    html.Button('Draft', id = 'draft-button', n_clicks_timestamp = 0, style={'marginLeft': '15px', 'marginBottom': '10px', 'width': '10%', 'display': 'inline-block', 'color': 'white', 'backgroundColor': 'green'}),
    html.Div([
        html.Div([
            dash_table.DataTable(
                    id='roster-table',
                    columns = [{'name': i, 'id': i} for i in ['Pos.', 'Name']],
                    data = roster_df.to_dict('records'),
                    style_cell = {'minWidth': '0px', 'maxWidth': '380px', 'whiteSpace': 'no-wrap',
                                  'overflow': 'hidden', 'textOverflow': 'ellipsis', 'color': 'black',
                                  'border': '1px solid black', 'textAlign': 'center'},
                    style_header={'color': 'black', 'border': '1px solid black', 'textAlign': 'center'},
                    style_table = {'overflowX': 'auto', 'overflowY': 'scroll', 'height': 425},
                    selected_rows = [],
                    style_data_conditional=[
                        {
                            'if': {
                                'filter_query': '{Pos.} = QB1'
                            },
                            'backgroundColor': 'lightgrey',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = QB2'
                            },
                            'backgroundColor': 'lightgrey',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = QB3'
                            },
                            'backgroundColor': 'lightgrey',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = RB1'
                            },
                            'backgroundColor': 'lightgreen',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = RB2'
                            },
                            'backgroundColor': 'lightgreen',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = RB3'
                            },
                            'backgroundColor': 'lightgreen',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = RB4'
                            },
                            'backgroundColor': 'lightgreen',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = RB5'
                            },
                            'backgroundColor': 'lightgreen',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = RB6'
                            },
                            'backgroundColor': 'lightgreen',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = RB7'
                            },
                            'backgroundColor': 'lightgreen',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR1'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR2'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR3'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR4'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR5'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR6'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR7'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR8'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR9'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR10'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR11'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR12'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = WR13'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = TE1'
                            },
                            'backgroundColor': 'plum',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = TE2'
                            },
                            'backgroundColor': 'plum',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Pos.} = TE3'
                            },
                            'backgroundColor': 'plum',
                            'color': 'black'
                        }
                    ]
                 )], style={'width': '18%', 'color':'gray'}, className = 'three columns'
        ),
        html.Div([
            dcc.Graph(
                    id='bar-chart')
                 ], style={'width': '42%', 'color':'gray'}, className = 'three columns'
        ),
        html.Div([
            dash_table.DataTable(
                    id='player-tracker',
                    columns = [{'name': i, 'id': i} for i in ['ADP', 'Name', 'Position', 'Team']],
                    data = adp_df.to_dict('records'),
                    style_cell = {'minWidth': '0px', 'maxWidth': '380px', 'whiteSpace': 'no-wrap',
                                  'overflow': 'hidden', 'textOverflow': 'ellipsis',
                                  'border': '1px solid black', 'textAlign': 'center'},
                    style_header={'color': 'black', 'border': '1px solid black', 'textAlign': 'center'},
                    style_table = {'overflowX': 'auto', 'overflowY': 'scroll', 'height': 425},
                    filter_action = 'native',
                    row_selectable = 'single',
                    selected_rows = [],
                    style_data_conditional=[
                        {
                            'if': {
                                'filter_query': '{Position} = QB'
                            },
                            'backgroundColor': 'lightgrey',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Position} = HB'
                            },
                            'backgroundColor': 'lightgreen',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Position} = WR'
                            },
                            'backgroundColor': 'lightskyblue',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Position} = TE'
                            },
                            'backgroundColor': 'plum',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Position} = D/ST'
                            },
                            'backgroundColor': 'khaki',
                            'color': 'black'
                        },
                        {
                            'if': {
                                'filter_query': '{Position} = K'
                            },
                            'backgroundColor': 'teal',
                            'color': 'black'
                        }
                    ])
                 ], style={'width': '30%', 'color':'gray'}, className = 'three columns'
        )
    ]),
    html.Div([dcc.Store(id='memory-data', data = data_stores)])
])

@app.callback(
    [dash.dependencies.Output('bar-chart', 'figure'),
    dash.dependencies.Output('player-tracker', 'selected_rows'),
    dash.dependencies.Output('player-tracker', 'data'),
    dash.dependencies.Output('roster-table', 'data'),
    dash.dependencies.Output('memory-data', 'data')],
    [dash.dependencies.Input('position-dropdown', 'value'),
    dash.dependencies.Input('value-dropdown', 'value'),
    dash.dependencies.Input('draft-button', 'n_clicks_timestamp'),
    dash.dependencies.Input('delete-button', 'n_clicks_timestamp'),
    dash.dependencies.Input('size-dropdown', 'value'),
    dash.dependencies.Input('team-dropdown', 'value')],
    [dash.dependencies.State('player-tracker', 'selected_rows'),
    dash.dependencies.State('memory-data', 'data')])

def render_bar_chart(position_selected, value_selected, n_clicks_draft, n_clicks_delete, size_filter, team_filter, selected_rows, data_stores):

    df = pd.DataFrame(data= data_stores['df'], columns = data_stores['df_columns'])
    adp_df = pd.DataFrame(data= data_stores['adp_df'], columns = data_stores['adp_df_columns'])
    roster_df = pd.DataFrame(data= data_stores['roster_df'], columns = data_stores['roster_df_columns'])
    roster_list = data_stores['roster_list']
    team_pos_count = data_stores['stacking_dict']

    size_filter = int(size_filter)
    if len(selected_rows) > 0:
        drop_player = adp_df.iloc[selected_rows, 1].to_string(index=False).strip()
        drop_pos = adp_df.iloc[selected_rows, 2].to_string(index=False).strip()
        df = df[df['Name'] != drop_player].reset_index(drop=True)
        adp_df = adp_df[adp_df['Name'] != drop_player]
        
    #Added PPG boost for team stacking
    if ((n_clicks_draft > n_clicks_delete) & (len(selected_rows) > 0)):
        print('we did it')
        if drop_team not in team_pos_count.keys():
            team_pos_count[drop_team] = {}
        if drop_pos not in team_pos_count[drop_team].keys():
            team_pos_count[drop_team][drop_pos] = 1
        else:
            team_pos_count[drop_team][drop_pos] += 1
        if (drop_pos == 'QB') & (team_pos_count[drop_team][drop_pos] == 1):
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG+'] += 1.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG PROJECTION'] += 1.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'HB'), 'PPG+'] += 1.0
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'HB'), 'PPG PROJECTION'] += 1.0
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG+'] += 1.0
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG PROJECTION'] += 1.0
        if (drop_pos == 'HB') & (team_pos_count[drop_team][drop_pos] == 1):
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG+'] += 0.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG PROJECTION'] += 0.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'QB'), 'PPG+'] += 1.0
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'QB'), 'PPG PROJECTION'] += 1.0
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG+'] += 0.25
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG PROJECTION'] += 0.25
        if (drop_pos == 'TE') & (team_pos_count[drop_team][drop_pos] == 1):
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG+'] += 0.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG PROJECTION'] += 0.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'QB'), 'PPG+'] += 1.0
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'QB'), 'PPG PROJECTION'] += 1.0
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG+'] += 0.25
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG PROJECTION'] += 0.25
        if (drop_pos == 'WR') & (team_pos_count[drop_team][drop_pos] == 1):
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'HB'), 'PPG+'] += 0.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'HB'), 'PPG PROJECTION'] += 0.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'QB'), 'PPG+'] += 1.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'QB'), 'PPG PROJECTION'] += 1.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG+'] += 0.25
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG PROJECTION'] += 0.25
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG+'] += 1.0
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG PROJECTION'] += 1.0
        if (drop_pos == 'WR') & (team_pos_count[drop_team][drop_pos] == 2):
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'HB'), 'PPG+'] += 0.25
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'HB'), 'PPG PROJECTION'] += 0.25
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'QB'), 'PPG+'] += 1.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'QB'), 'PPG PROJECTION'] += 1.5
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG+'] += 0.25
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'TE'), 'PPG PROJECTION'] += 0.25
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG+'] += 0.75
            df.loc[(df['Team'] == drop_team) & (df['Position'] == 'WR'), 'PPG PROJECTION'] += 0.75
        print('I knew we could')

    if position_selected == 'ALL':
        filtered_df = df[(df['Position'] != 'D/ST') & (df['Position'] != 'K')].copy()
    elif position_selected == 'FLEX':
        filtered_df = df[(df['Position'] == 'HB') | (df['Position'] == 'WR') | (df['Position'] == 'TE')]
    else:
        filtered_df = df[(df['Position'] == position_selected)]
    if team_filter != 'ALL TEAMS':
        filtered_df = filtered_df[filtered_df['Team'] == team_filter]
    color_dict = {'QB': 'lightgrey',
          'HB': 'lightgreen',
          'WR': 'lightskyblue',
          'TE': 'plum',
          'D/ST': 'khaki',
          'K': 'teal'}
    if value_selected == 'POINTS PER GAME':
        if team_filter != 'ALL TEAMS':
            filtered_df = filtered_df.sort_values(by='PPG PROJECTION', ascending=False)[::-1]
        else:
            filtered_df = filtered_df.sort_values(by='PPG PROJECTION', ascending=False)[:size_filter][::-1]
        filtered_df['Text'] = '(' + df['ADP'].round(1).astype(str) + ') ' + df['Name'] + ': ' + filtered_df['PPG PROJECTION'].round(1).astype(str)
        positions = filtered_df['Position'].tolist()
        bar_colors = []
        for pos in positions:
            bar_colors.append(color_dict[pos])
        bardata = go.Bar(y=filtered_df['Name'],
                         x=filtered_df['PPG PROJECTION'],
                         orientation = 'h',
                         text = filtered_df['Text'],
                         marker_color = bar_colors,
                         marker_line_color = 'black',
                         marker_line_width = 1,
                         textposition = 'auto')
    else:
        if team_filter != 'ALL TEAMS':
            filtered_df = filtered_df.sort_values(by='PPG+', ascending=False)[::-1]
        else:
            filtered_df = filtered_df.sort_values(by='PPG+', ascending=False)[:size_filter][::-1]
        filtered_df['Text'] = '(' + df['ADP'].round(1).astype(str) + ') ' + df['Name'] + ': ' + filtered_df['PPG+'].round(1).astype(str)
        positions = filtered_df['Position'].tolist()
        bar_colors = []
        for pos in positions:
            bar_colors.append(color_dict[pos])
        bardata = go.Bar(y=filtered_df['Name'],
                         x=filtered_df['PPG+'],
                         orientation = 'h',
                         text = filtered_df['Text'],
                         marker_color = bar_colors,
                         marker_line_color = 'black',
                         marker_line_width = 1,
                         textposition = 'auto')
        
    if ((n_clicks_draft > n_clicks_delete) & (len(selected_rows) > 0)):
        drafted_player = drop_player
        drafted_player_pos = drop_pos
        if ((roster_list[0] == '-') & (drafted_player_pos == 'QB')):
            roster_list[0] = drafted_player
        elif ((roster_list[1] == '-') & (drafted_player_pos == 'QB')):
            roster_list[1] = drafted_player
        elif ((roster_list[2] == '-') & (drafted_player_pos == 'QB')):
            roster_list[2] = drafted_player
        elif ((roster_list[3] == '-') & (drafted_player_pos == 'HB')):
            roster_list[3] = drafted_player
        elif ((roster_list[4] == '-') & (drafted_player_pos == 'HB')):
            roster_list[4] = drafted_player
        elif ((roster_list[5] == '-') & (drafted_player_pos == 'HB')):
            roster_list[5] = drafted_player
        elif ((roster_list[6] == '-') & (drafted_player_pos == 'HB')):
            roster_list[6] = drafted_player
        elif ((roster_list[7] == '-') & (drafted_player_pos == 'HB')):
            roster_list[7] = drafted_player
        elif ((roster_list[8] == '-') & (drafted_player_pos == 'HB')):
            roster_list[8] = drafted_player
        elif ((roster_list[9] == '-') & (drafted_player_pos == 'HB')):
            roster_list[9] = drafted_player
        elif ((roster_list[10] == '-') & (drafted_player_pos == 'WR')):
            roster_list[10] = drafted_player
        elif ((roster_list[11] == '-') & (drafted_player_pos == 'WR')):
            roster_list[11] = drafted_player
        elif ((roster_list[12] == '-') & (drafted_player_pos == 'WR')):
            roster_list[12] = drafted_player
        elif ((roster_list[13] == '-') & (drafted_player_pos == 'WR')):
            roster_list[13] = drafted_player
        elif ((roster_list[14] == '-') & (drafted_player_pos == 'WR')):
            roster_list[14] = drafted_player
        elif ((roster_list[15] == '-') & (drafted_player_pos == 'WR')):
            roster_list[15] = drafted_player
        elif ((roster_list[16] == '-') & (drafted_player_pos == 'WR')):
            roster_list[16] = drafted_player
        elif ((roster_list[17] == '-') & (drafted_player_pos == 'WR')):
            roster_list[17] = drafted_player
        elif ((roster_list[18] == '-') & (drafted_player_pos == 'WR')):
            roster_list[18] = drafted_player
        elif ((roster_list[19] == '-') & (drafted_player_pos == 'WR')):
            roster_list[19] = drafted_player
        elif ((roster_list[20] == '-') & (drafted_player_pos == 'WR')):
            roster_list[20] = drafted_player
        elif ((roster_list[21] == '-') & (drafted_player_pos == 'WR')):
            roster_list[21] = drafted_player
        elif ((roster_list[22] == '-') & (drafted_player_pos == 'WR')):
            roster_list[22] = drafted_player
        elif ((roster_list[23] == '-') & (drafted_player_pos == 'TE')):
            roster_list[23] = drafted_player
        elif ((roster_list[24] == '-') & (drafted_player_pos == 'TE')):
            roster_list[24] = drafted_player
        elif ((roster_list[25] == '-') & (drafted_player_pos == 'TE')):
            roster_list[25] = drafted_player
        roster_df['Name'] = roster_list

    data_stores['roster_list'] = roster_list
    data_stores['adp_df'] = adp_df.values
    data_stores['adp_df_columns'] = adp_df.columns
    data_stores['roster_df'] = roster_df.values
    data_stores['roster_df_columns'] = roster_df.columns
    data_stores['df'] = df.values
    data_stores['df_columns'] = df.columns
    data_stores['stacking_dict'] = team_pos_count

    return {
        'data':[bardata],
        'layout': {'height': 425,
                  'margin': {'l': 1, 'b': 30, 'r': 10, 't': 10}}
        }, [], adp_df.to_dict('records'), roster_df.to_dict('records'), data_stores


if __name__ == '__main__':
    app.run_server(debug=True)
