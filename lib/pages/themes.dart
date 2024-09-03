import 'package:flutter/material.dart';
import 'package:sifgeo/components/homeappbar.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

class ThemePage extends StatefulWidget {
  @override
  _MyAppState createState() => _MyAppState();
}

class _MyAppState extends State<ThemePage> {
 MapController mapController = MapController();
  final TileLayer _lulc50kLayer = TileLayer(
    wmsOptions: WMSTileLayerOptions(
      baseUrl: 'https://bhuvan-vec2.nrsc.gov.in/bhuvan/gwc/service/wms/?',
      layers: const ['lulc:DL_LULC50K_1516'],
      version: '1.1.1',
      format: 'image/png',
      
    ),
  );

  final TileLayer _lulc10kLayer = TileLayer(
    wmsOptions: WMSTileLayerOptions(
      baseUrl: 'https://bhuvan-vec2.nrsc.gov.in/bhuvan/gwc/service/wms/?',
      layers: const ['sisdp_phase2:SISDP_P2_LULC_10K_2016_2019_DL'],
      version: '1.1.1',
      format: 'image/png',
    ),

  );

  late TileLayer _currentLayer;

  @override
  void initState() {
    super.initState();
    _currentLayer = _lulc50kLayer; 
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Color.fromRGBO(66, 66, 66, 1),
      appBar: const PreferredSize(
        preferredSize: Size.fromHeight(45),
        child: Appbar(),
      ),
      body: Column(
        children: [
          Flexible(
            child: FlutterMap(
              mapController: mapController,
          options: MapOptions(
            initialCenter: LatLng(20.5937, 78.9629),
            initialZoom: 5.0,
            minZoom: 2.0,
            maxZoom: 16.0,
            backgroundColor: Colors.transparent,
          ),
          children: [
            TileLayer(
              urlTemplate: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            ),  _currentLayer,
              ],
            ),
          ),
          DropdownButton<TileLayer>(
            value: _currentLayer,
            onChanged: (TileLayer? value) {
              setState(() {
                _currentLayer = value!;
              });
            },
            items: [
              DropdownMenuItem(
                value: _lulc50kLayer,
                child: Text('LULC 50k 15-16'),
              ),
              DropdownMenuItem(
                value: _lulc10kLayer,
                child: Text('LULC 10k sisdp phase2'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
