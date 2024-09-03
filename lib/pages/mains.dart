import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:file_picker/file_picker.dart';
import 'package:archive/archive.dart';
import 'package:xml/xml.dart' as xml;

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: MapWidget(),
      ),
    );
  }
}

class MapWidget extends StatefulWidget {
  @override
  _MapWidgetState createState() => _MapWidgetState();
}

class _MapWidgetState extends State<MapWidget> {
  List<LatLng> coordinates = [];
  MapController mapController = MapController();

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        FlutterMap(
          mapController: mapController,
          options: MapOptions(
            initialCenter: LatLng(0, 0), // Initial map center
            initialZoom: 2.0, // Initial zoom level
            backgroundColor: Colors.transparent,
          ),
          children: [
            TileLayer(
              urlTemplate: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            ),
            if (coordinates.isNotEmpty)
              MarkerLayer(
                markers: coordinates.map((point) {
                  return Marker(
                    point: LatLng(point.latitude, point.longitude),
                    child: Icon(
                      Icons.location_on,
                      color: Colors.blue,
                      size: 30.0,
                    ),
                  );
                }).toList(),
              ),
          ],
        ),
        Positioned(
          bottom: 16.0,
          right: 16.0,
          child: PopupMenuButton<String>(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Container(
                    width: 100.0,
                    height: 50.0,
                    color: Colors.white,
                    child: Center(
                        child: Text(
                      'Add File',
                      style: TextStyle(color: Colors.black),
                    )))
              ],
            ),
            onSelected: (value) {
              if (value == 'pickKMZ') {
                _handlePickKMZFile();
              } else if (value == 'additionalOption1') {
                _handleAdditionalButton1();
              } else if (value == 'additionalOption2') {
                _handleAdditionalButton2();
              } else if (value == 'additionalOption3') {
                _handleAdditionalButton3();
              }
            },
            itemBuilder: (BuildContext context) => <PopupMenuEntry<String>>[
              PopupMenuItem<String>(
                value: 'pickKMZ',
                child: ListTile(
                  title: Text('KMZ File'),
                ),
              ),
              PopupMenuItem<String>(
                value: 'additionalOption1',
                child: ListTile(
                  title: Text('Option 1'),
                ),
              ),
              PopupMenuItem<String>(
                value: 'additionalOption2',
                child: ListTile(
                  title: Text('Option 2'),
                ),
              ),
              PopupMenuItem<String>(
                value: 'additionalOption3',
                child: ListTile(
                  title: Text('Option 3'),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  void _handlePickKMZFile() async {
    List<LatLng> pickedCoordinates = await pickKMZFile();
    if (pickedCoordinates.isNotEmpty) {
      setState(() {
        coordinates = pickedCoordinates;
        mapController.move(coordinates.first, 10.0);
      });
    }
  }

  void _handleAdditionalButton1() {
    // Implement the action for the additional button
    print('Additional button pressed!');
  }

  void _handleAdditionalButton2() {
    // Implement the action for the additional button
    print('Additional button pressed!');
  }

  void _handleAdditionalButton3() {
    // Implement the action for the additional button
    print('Additional button pressed!');
  }

  Future<List<LatLng>> pickKMZFile() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['kmz'],
      );

      if (result != null && result.files.single.bytes != null) {
        Uint8List kmzBytes = result.files.single.bytes!;
        List<int> kmlBytes = extractKmlBytes(kmzBytes);
        List<LatLng> coordinates = parseKmlData(kmlBytes);
        return coordinates;
      }
    } catch (e) {
      print('Error picking KMZ file: $e');
    }

    return [];
  }

  List<int> extractKmlBytes(Uint8List kmzBytes) {
    Archive archive = ZipDecoder().decodeBytes(kmzBytes);
    for (ArchiveFile file in archive) {
      if (file.name.toLowerCase().endsWith('.kml')) {
        return file.content;
      }
    }
    return [];
  }

  List<LatLng> parseKmlData(List<int> kmlBytes) {
    String kmlString = String.fromCharCodes(kmlBytes);
    xml.XmlDocument xmlDoc = xml.XmlDocument.parse(kmlString);
    List<LatLng> coordinates = [];
    var placemarks = xmlDoc.findAllElements('Placemark');

    for (var placemark in placemarks) {
      var point = placemark.findElements('Point').first;
      var coordinateNode = point.findElements('coordinates').first;
      String coordinatesStr = coordinateNode.text.trim();
      List<String> coordsList = coordinatesStr.split(',');

      double lat = double.parse(coordsList[1]);
      double lon = double.parse(coordsList[0]);
      coordinates.add(LatLng(lat, lon));
    }

    return coordinates;
  }
}
