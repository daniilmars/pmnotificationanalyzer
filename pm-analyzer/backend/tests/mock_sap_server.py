"""
Mock SAP OData Server for Testing

Simulates SAP PM OData services for development and testing without
requiring a real SAP system connection.

Run with: python mock_sap_server.py
Server starts at: http://localhost:8080

Endpoints:
- /sap/opu/odata/sap/PM_NOTIFICATION_SRV/NotificationSet
- /sap/opu/odata/sap/PM_ORDER_SRV/OrderSet
- /sap/opu/odata/sap/EQUIPMENT_SRV/EquipmentSet
- /sap/opu/odata/sap/$metadata
"""

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from datetime import datetime, timedelta
import random
import json

app = Flask(__name__)
CORS(app)

# ============================================
# Mock Data
# ============================================

NOTIFICATION_TYPES = ['M1', 'M2', 'M3', 'S1', 'S2', 'S3']
PRIORITIES = ['1', '2', '3', '4']
STATUSES = ['OSNO', 'ORAS', 'NOPR', 'NOCO']

EQUIPMENT_DATA = {
    'PUMP-001': {'description': 'Centrifugal Pump Unit 1', 'category': 'M', 'location': 'PLANT-A-L01'},
    'PUMP-002': {'description': 'Centrifugal Pump Unit 2', 'category': 'M', 'location': 'PLANT-A-L01'},
    'COMP-001': {'description': 'Air Compressor Main', 'category': 'M', 'location': 'PLANT-A-L02'},
    'CONV-001': {'description': 'Conveyor Belt System', 'category': 'M', 'location': 'PLANT-B-L01'},
    'HEAT-001': {'description': 'Heat Exchanger Unit', 'category': 'M', 'location': 'PLANT-B-L02'},
    'TANK-001': {'description': 'Storage Tank A', 'category': 'K', 'location': 'PLANT-C-L01'},
    'TANK-002': {'description': 'Storage Tank B', 'category': 'K', 'location': 'PLANT-C-L01'},
    'VALVE-001': {'description': 'Main Control Valve', 'category': 'M', 'location': 'PLANT-A-L03'},
    'MOTOR-001': {'description': 'Electric Motor 500kW', 'category': 'M', 'location': 'PLANT-A-L01'},
    'SENSOR-001': {'description': 'Temperature Sensor Array', 'category': 'E', 'location': 'PLANT-B-L01'},
}

DAMAGE_CODES = [
    ('MECH', '001', 'Mechanical wear'),
    ('MECH', '002', 'Bearing failure'),
    ('MECH', '003', 'Shaft misalignment'),
    ('ELEC', '001', 'Electrical fault'),
    ('ELEC', '002', 'Motor burnout'),
    ('LEAK', '001', 'Seal leakage'),
    ('LEAK', '002', 'Pipe corrosion'),
    ('VIBR', '001', 'Excessive vibration'),
    ('TEMP', '001', 'Overheating'),
    ('PRES', '001', 'Pressure deviation'),
]

CAUSE_CODES = [
    ('OPER', '001', 'Operator error'),
    ('WEAR', '001', 'Normal wear and tear'),
    ('WEAR', '002', 'Accelerated wear'),
    ('MATL', '001', 'Material defect'),
    ('MATL', '002', 'Corrosion'),
    ('MAIN', '001', 'Insufficient maintenance'),
    ('MAIN', '002', 'Delayed maintenance'),
    ('ENVR', '001', 'Environmental conditions'),
    ('LOAD', '001', 'Overload condition'),
    ('DSGN', '001', 'Design limitation'),
]

# Generate mock notifications
def generate_notifications(count=50):
    notifications = []
    base_date = datetime.now() - timedelta(days=365)

    for i in range(1, count + 1):
        notif_date = base_date + timedelta(days=random.randint(0, 365))
        equipment = random.choice(list(EQUIPMENT_DATA.keys()))
        damage = random.choice(DAMAGE_CODES)
        cause = random.choice(CAUSE_CODES)

        notifications.append({
            'NotificationNo': str(10000000 + i).zfill(12),
            'NotificationType': random.choice(NOTIFICATION_TYPES),
            'NotificationText': f'Maintenance required for {EQUIPMENT_DATA[equipment]["description"]}',
            'LongText': f'Detailed description: Equipment {equipment} requires maintenance. '
                       f'Issue: {damage[2]}. Root cause analysis indicates: {cause[2]}. '
                       f'Immediate attention recommended.',
            'Priority': random.choice(PRIORITIES),
            'Equipment': equipment,
            'FunctionalLocation': EQUIPMENT_DATA[equipment]['location'],
            'CreatedOn': notif_date.strftime('/Date(%d)/' % (notif_date.timestamp() * 1000)),
            'CreatedOnFormatted': notif_date.strftime('%Y-%m-%d'),
            'CreatedBy': random.choice(['JSMITH', 'MJONES', 'KWILSON', 'ABROWN', 'TLEE']),
            'SystemStatus': random.choice(STATUSES),
            'DamageCodeGroup': damage[0],
            'DamageCode': damage[1],
            'DamageText': damage[2],
            'CauseCodeGroup': cause[0],
            'CauseCode': cause[1],
            'CauseText': cause[2],
            'RequiredStartDate': (notif_date + timedelta(days=1)).strftime('/Date(%d)/' % ((notif_date + timedelta(days=1)).timestamp() * 1000)),
            'RequiredEndDate': (notif_date + timedelta(days=7)).strftime('/Date(%d)/' % ((notif_date + timedelta(days=7)).timestamp() * 1000)),
            '__metadata': {
                'uri': f"/sap/opu/odata/sap/PM_NOTIFICATION_SRV/NotificationSet('{str(10000000 + i).zfill(12)}')",
                'type': 'PM_NOTIFICATION_SRV.Notification'
            }
        })

    return notifications

def generate_orders(count=30):
    orders = []
    base_date = datetime.now() - timedelta(days=180)

    for i in range(1, count + 1):
        order_date = base_date + timedelta(days=random.randint(0, 180))
        equipment = random.choice(list(EQUIPMENT_DATA.keys()))

        orders.append({
            'OrderNo': str(4000000 + i).zfill(12),
            'OrderType': random.choice(['PM01', 'PM02', 'PM03']),
            'ShortText': f'Work order for {EQUIPMENT_DATA[equipment]["description"]}',
            'Equipment': equipment,
            'FunctionalLocation': EQUIPMENT_DATA[equipment]['location'],
            'NotificationNo': str(10000000 + random.randint(1, 50)).zfill(12),
            'BasicStartDate': order_date.strftime('/Date(%d)/' % (order_date.timestamp() * 1000)),
            'BasicEndDate': (order_date + timedelta(days=3)).strftime('/Date(%d)/' % ((order_date + timedelta(days=3)).timestamp() * 1000)),
            'SystemStatus': random.choice(['CRTD', 'REL', 'TECO', 'CLSD']),
            'Priority': random.choice(PRIORITIES),
            'PlannerGroup': random.choice(['001', '002', '003']),
            'WorkCenter': random.choice(['MECH01', 'ELEC01', 'INST01']),
            '__metadata': {
                'uri': f"/sap/opu/odata/sap/PM_ORDER_SRV/OrderSet('{str(4000000 + i).zfill(12)}')",
                'type': 'PM_ORDER_SRV.Order'
            }
        })

    return orders

# Pre-generate data
MOCK_NOTIFICATIONS = generate_notifications(50)
MOCK_ORDERS = generate_orders(30)


# ============================================
# OData Metadata
# ============================================

ODATA_METADATA = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
  <edmx:DataServices m:DataServiceVersion="2.0" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <Schema Namespace="PM_NOTIFICATION_SRV" xmlns="http://schemas.microsoft.com/ado/2008/09/edm">
      <EntityType Name="Notification">
        <Key><PropertyRef Name="NotificationNo"/></Key>
        <Property Name="NotificationNo" Type="Edm.String" Nullable="false"/>
        <Property Name="NotificationType" Type="Edm.String"/>
        <Property Name="NotificationText" Type="Edm.String"/>
        <Property Name="Priority" Type="Edm.String"/>
        <Property Name="Equipment" Type="Edm.String"/>
        <Property Name="FunctionalLocation" Type="Edm.String"/>
        <Property Name="CreatedOn" Type="Edm.DateTime"/>
        <Property Name="CreatedBy" Type="Edm.String"/>
        <Property Name="SystemStatus" Type="Edm.String"/>
      </EntityType>
      <EntityContainer Name="PM_NOTIFICATION_SRV" m:IsDefaultEntityContainer="true">
        <EntitySet Name="NotificationSet" EntityType="PM_NOTIFICATION_SRV.Notification"/>
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>"""


# ============================================
# Routes
# ============================================

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'server': 'Mock SAP OData Server'})


@app.route('/sap/opu/odata/sap/<service>/$metadata')
def metadata(service):
    return Response(ODATA_METADATA, mimetype='application/xml')


@app.route('/sap/opu/odata/sap/PM_NOTIFICATION_SRV/NotificationSet', methods=['GET'])
def get_notifications():
    """Get all notifications or filter by query parameters"""
    # Parse OData parameters
    top = request.args.get('$top', type=int, default=100)
    skip = request.args.get('$skip', type=int, default=0)
    filter_param = request.args.get('$filter', '')

    results = MOCK_NOTIFICATIONS.copy()

    # Apply basic filtering
    if filter_param:
        if 'NotificationType eq' in filter_param:
            notif_type = filter_param.split("'")[1]
            results = [n for n in results if n['NotificationType'] == notif_type]
        if 'Equipment eq' in filter_param:
            equipment = filter_param.split("'")[1]
            results = [n for n in results if n['Equipment'] == equipment]

    # Apply pagination
    total = len(results)
    results = results[skip:skip + top]

    return jsonify({
        'd': {
            'results': results,
            '__count': str(total)
        }
    })


@app.route('/sap/opu/odata/sap/PM_NOTIFICATION_SRV/NotificationSet(<notification_id>)', methods=['GET'])
@app.route("/sap/opu/odata/sap/PM_NOTIFICATION_SRV/NotificationSet('<notification_id>')", methods=['GET'])
def get_notification(notification_id):
    """Get single notification by ID"""
    # Clean the ID
    notification_id = notification_id.strip("'").zfill(12)

    for notif in MOCK_NOTIFICATIONS:
        if notif['NotificationNo'] == notification_id:
            return jsonify({'d': notif})

    return jsonify({'error': {'code': '404', 'message': 'Notification not found'}}), 404


@app.route('/sap/opu/odata/sap/PM_NOTIFICATION_SRV/NotificationSet', methods=['POST'])
def create_notification():
    """Create a new notification"""
    data = request.get_json()

    # Generate new notification ID
    new_id = str(10000000 + len(MOCK_NOTIFICATIONS) + 1).zfill(12)

    new_notification = {
        'NotificationNo': new_id,
        'NotificationType': data.get('NotificationType', 'M1'),
        'NotificationText': data.get('NotificationText', ''),
        'Priority': data.get('Priority', '4'),
        'Equipment': data.get('Equipment', ''),
        'FunctionalLocation': data.get('FunctionalLocation', ''),
        'CreatedOn': f'/Date({int(datetime.now().timestamp() * 1000)})/',
        'CreatedOnFormatted': datetime.now().strftime('%Y-%m-%d'),
        'CreatedBy': 'TESTUSER',
        'SystemStatus': 'OSNO',
        '__metadata': {
            'uri': f"/sap/opu/odata/sap/PM_NOTIFICATION_SRV/NotificationSet('{new_id}')",
            'type': 'PM_NOTIFICATION_SRV.Notification'
        }
    }

    MOCK_NOTIFICATIONS.append(new_notification)

    return jsonify({'d': new_notification}), 201


@app.route('/sap/opu/odata/sap/PM_ORDER_SRV/OrderSet', methods=['GET'])
def get_orders():
    """Get all work orders"""
    top = request.args.get('$top', type=int, default=100)
    skip = request.args.get('$skip', type=int, default=0)

    results = MOCK_ORDERS[skip:skip + top]

    return jsonify({
        'd': {
            'results': results,
            '__count': str(len(MOCK_ORDERS))
        }
    })


@app.route('/sap/opu/odata/sap/PM_ORDER_SRV/OrderSet(<order_id>)', methods=['GET'])
@app.route("/sap/opu/odata/sap/PM_ORDER_SRV/OrderSet('<order_id>')", methods=['GET'])
def get_order(order_id):
    """Get single order by ID"""
    order_id = order_id.strip("'").zfill(12)

    for order in MOCK_ORDERS:
        if order['OrderNo'] == order_id:
            return jsonify({'d': order})

    return jsonify({'error': {'code': '404', 'message': 'Order not found'}}), 404


@app.route('/sap/opu/odata/sap/EQUIPMENT_SRV/EquipmentSet', methods=['GET'])
def get_equipment_list():
    """Get all equipment"""
    results = []
    for equip_id, data in EQUIPMENT_DATA.items():
        results.append({
            'EquipmentNo': equip_id,
            'Description': data['description'],
            'Category': data['category'],
            'FunctionalLocation': data['location'],
            '__metadata': {
                'uri': f"/sap/opu/odata/sap/EQUIPMENT_SRV/EquipmentSet('{equip_id}')",
                'type': 'EQUIPMENT_SRV.Equipment'
            }
        })

    return jsonify({
        'd': {
            'results': results,
            '__count': str(len(results))
        }
    })


@app.route('/sap/opu/odata/sap/EQUIPMENT_SRV/EquipmentSet(<equipment_id>)', methods=['GET'])
@app.route("/sap/opu/odata/sap/EQUIPMENT_SRV/EquipmentSet('<equipment_id>')", methods=['GET'])
def get_equipment(equipment_id):
    """Get single equipment by ID"""
    equipment_id = equipment_id.strip("'")

    if equipment_id in EQUIPMENT_DATA:
        data = EQUIPMENT_DATA[equipment_id]
        return jsonify({
            'd': {
                'EquipmentNo': equipment_id,
                'Description': data['description'],
                'Category': data['category'],
                'FunctionalLocation': data['location'],
                '__metadata': {
                    'uri': f"/sap/opu/odata/sap/EQUIPMENT_SRV/EquipmentSet('{equipment_id}')",
                    'type': 'EQUIPMENT_SRV.Equipment'
                }
            }
        })

    return jsonify({'error': {'code': '404', 'message': 'Equipment not found'}}), 404


# ============================================
# Change Documents (for Audit Trail testing)
# ============================================

MOCK_CHANGES = []

@app.route('/sap/opu/odata/sap/CHANGE_DOCUMENT_SRV/ChangeDocumentSet', methods=['GET'])
def get_change_documents():
    """Get change documents"""
    object_class = request.args.get('objectClass', '')
    object_id = request.args.get('objectId', '')

    # Generate some mock change documents
    changes = []
    for i in range(10):
        change_date = datetime.now() - timedelta(days=random.randint(1, 30))
        changes.append({
            'ChangeNumber': f'000000{1000 + i}',
            'ObjectClass': object_class or 'QMEL',
            'ObjectId': object_id or str(10000000 + random.randint(1, 50)).zfill(12),
            'Username': random.choice(['JSMITH', 'MJONES', 'KWILSON']),
            'ChangeDate': change_date.strftime('%Y%m%d'),
            'ChangeTime': change_date.strftime('%H%M%S'),
            'TransactionCode': random.choice(['IW21', 'IW22', 'IW23']),
            'FieldChanges': [
                {
                    'FieldName': 'PRIOK',
                    'OldValue': '3',
                    'NewValue': '2'
                }
            ]
        })

    return jsonify({
        'd': {
            'results': changes
        }
    })


# ============================================
# Main
# ============================================

if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║           Mock SAP OData Server for Testing                   ║
╠══════════════════════════════════════════════════════════════╣
║  Server URL: http://localhost:8080                           ║
║                                                               ║
║  Available Endpoints:                                         ║
║  • GET  /health                                               ║
║  • GET  /sap/opu/odata/sap/PM_NOTIFICATION_SRV/NotificationSet║
║  • GET  /sap/opu/odata/sap/PM_ORDER_SRV/OrderSet             ║
║  • GET  /sap/opu/odata/sap/EQUIPMENT_SRV/EquipmentSet        ║
║  • POST /sap/opu/odata/sap/PM_NOTIFICATION_SRV/NotificationSet║
║                                                               ║
║  Configure your app with:                                     ║
║    SAP_ODATA_URL=http://localhost:8080                       ║
║    SAP_ODATA_PATH=/sap/opu/odata/sap/                        ║
║    SAP_USER=TESTUSER                                          ║
║    SAP_PASSWORD=testpass                                      ║
║    SAP_ENABLED=true                                           ║
║                                                               ║
║  Press Ctrl+C to stop                                         ║
╚══════════════════════════════════════════════════════════════╝
    """)

    app.run(host='0.0.0.0', port=8080, debug=True)
