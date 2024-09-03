import 'package:flutter/material.dart';
//import 'package:sifgeo/pages/shapeshift.dart';
import '/pages/themes.dart';
import 'dart:convert';
//import 'package:flutter_application_1/pages/voice_assist.dart';
import '../../components/homeappbar.dart';
import '../../components/drawer.dart';
import 'dart:typed_data';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:file_picker/file_picker.dart';
import 'package:archive/archive.dart';
import 'package:xml/xml.dart' as xml;
import 'package:http/http.dart' as http;

class HomePage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Color.fromRGBO(66, 66, 66, 1),
      drawer: NavDrawer(),
      appBar: const PreferredSize(
        preferredSize: Size.fromHeight(45),
        child: Appbar(),
      ),
      body: MapWidget(),
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
  List<LatLng> shapeCoordinates = [];

  Future<List<LatLng>> loadShape(String filePath) async {
    File file = File(filePath);
    String jsonString = await file.readAsString();
    var shape = json.decode(jsonString);

    List<LatLng> coordinates = parseShapeData(shape);
    return coordinates;
  }

  List<LatLng> parseShapeData(Map<String, dynamic> shape) {
    List<LatLng> coordinates = [];
    if (shape['type'] == 'FeatureCollection') {
      var features = shape['features'];
      for (var feature in features) {
        if (feature['type'] == 'Feature' &&
            feature['geometry']['type'] == 'Point') {
          var coords = feature['geometry']['coordinates'];
          double lon = coords[0];
          double lat = coords[1];
          coordinates.add(LatLng(lat, lon));
        }
      }
    }
    return coordinates;
  }



  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        FlutterMap(
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
            ),
            if (coordinates.isNotEmpty)
              MarkerLayer(
                markers: coordinates.map((point) {
                  return Marker(
                    point: LatLng(point.latitude, point.longitude),
                    child: GestureDetector(
                        onTap: () {
                          _showPopup(context, point.latitude, point.longitude);
                        },

                      child: Icon(
                        Icons.location_on,
                        color: Colors.red,
                        size: 30.0,
                      ),
                    ),
                  );
                }).toList(),
              ),
          ],
        ),
        Positioned(
          bottom: 6.0,
          right: 0.2,
          child: TextButton(
  style: TextButton.styleFrom(foregroundColor: Colors.green),
  child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Container(
                    width: 140.0,
                    height: 50.0,
                    decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(25.0),
                        color: Color.fromRGBO(66, 66, 66, 1)),
                    child: Center(
                        child: Text(
                      'Select Theme',
                      style: TextStyle(color: Colors.white),
                    )))
              ],
            ),
  onPressed: () {         Navigator.push(
                          context,
                          MaterialPageRoute(builder: (context) => ThemePage())
          );
  },
),),
        Positioned(
          bottom: 60.0,
          right: 12.0,
          child: PopupMenuButton<String>(
            elevation: 3.0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(25.0),
            ),
            shadowColor: Color(0x000000),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Container(
                    width: 100.0,
                    height: 50.0,
                    decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(25.0),
                        color: Color.fromRGBO(66, 66, 66, 1)),
                    child: Center(
                        child: Text(
                      'Add File',
                      style: TextStyle(color: Colors.white),
                    )))
              ],
            ),
            onSelected: (value) {
              if (value == 'pickKMZ') {
                _handlePickKMZFile();
               }else if (value == 'Shape') {
                handleAdditionalButton2();
              } 
              else if (value == 'Geoj') {
                _handlePickGeoJsonFile();
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
                value: 'Shape',
                child: ListTile(
                  title: Text('Shape File'),
                ),
              ),
              PopupMenuItem<String>(
                value: 'Geoj',
                child: ListTile(
                  title: Text('GeoJSON File'),
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

   void _handlePickGeoJsonFile() async {
    List<LatLng> pickedCoordinates = await pickGeoJsonFile();
    if (pickedCoordinates.isNotEmpty) {
      setState(() {
        coordinates = pickedCoordinates;
        mapController.move(coordinates.first, 10.0);
      });
    }
  }

  void handleAdditionalButton2() async {
    List<LatLng> pickedCoordinates = await pickGeoJsonFile1();
    if (pickedCoordinates.isNotEmpty) {
      setState(() {
        coordinates = pickedCoordinates;
        mapController.move(coordinates.first, 10.0);
      });
    } 
         
        
          
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
      String coordinatesStr = coordinateNode.innerText.trim();
      List<String> coordsList = coordinatesStr.split(',');

      double lat = double.parse(coordsList[1]);
      double lon = double.parse(coordsList[0]);
      coordinates.add(LatLng(lat, lon));
    }

    return coordinates;
  }


  Future<List<LatLng>> pickGeoJsonFile1() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
    type: FileType.custom,
    allowedExtensions: ['shp', 'shx', 'dbf', 'prj'], 
      );

      if (result != null) {
        List<LatLng> coordinates = await loadShape('/RestaurantData_GeoJSON.geojson');
        return coordinates;
      }
    }
    catch(e){
      print(e); }
    return [];}

  // This method picks a GeoJSON file and parses its coordinates
  Future<List<LatLng>> pickGeoJsonFile() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['geojson', 'json'],
      );

      if (result != null && result.files.single.bytes != null) {
        Uint8List fileBytes = result.files.single.bytes!;
        List<LatLng> coordinates = parseGeoJsonData(fileBytes);
        return coordinates;
      }
    } catch (e) {
      print('Error picking GeoJSON file: $e');
    }

    return [];
  }

  // Parse the GeoJSON data to extract coordinates
  List<LatLng> parseGeoJsonData(Uint8List fileBytes) {
  List<LatLng> coordinates = [];
  String jsonString = String.fromCharCodes(fileBytes);
  var geoJson = jsonDecode(jsonString);

  if (geoJson['type'] == 'FeatureCollection') {
    var features = geoJson['features'];
    for (var feature in features) {
      if (feature['type'] == 'Feature' && feature['geometry']['type'] == 'Point') {
        var coords = feature['geometry']['coordinates'];
        double lon = coords[0];
        double lat = coords[1];
        coordinates.add(LatLng(lat, lon));
      }
    }
  }

  return coordinates;
}


// Future<List<LatLng>> pickGeoJsonFile1(String geoJsonString) async {
//   try {
//     List<LatLng> coordinates = parseGeoJsonData1(geoJsonString);
//     return coordinates;
//   } catch (e) {
//     print('Error parsing GeoJSON data: $e');
//     return [];
//   }
// }

// // Updated to accept a GeoJSON string directly
// List<LatLng> parseGeoJsonData1(String geoJsonString) {
//   List<LatLng> coordinates = [];
//   var geoJson = jsonDecode(geoJsonString);

//   if (geoJson['type'] == 'FeatureCollection') {
//     var features = geoJson['features'];
//     for (var feature in features) {
//       if (feature['type'] == 'Feature' && feature['geometry']['type'] == 'Point') {
//         var coords = feature['geometry']['coordinates'];
//         double lon = coords[0];
//         double lat = coords[1];
//         coordinates.add(LatLng(lat, lon));
//       }
//     }
//   }

//   return coordinates;
// }
Future<String?> fetchAddress(double latitude, double longitude) async {
    showDialog(
      context: context,
      builder: (context) {
        return Center(child: CircularProgressIndicator());
      },
    );
    final apiUrl =
        'https://nominatim.openstreetmap.org/reverse?format=json&lat=$latitude&lon=$longitude&zoom=18&addressdetails=1';

    try {
      var response = await http.get(Uri.parse(apiUrl));
      if (response.statusCode == 200) {
        var data = json.decode(response.body);
        if (data['address'] != null) {
          return data['address']['display_name'];
        }
      }
    } catch (e) {
      print('Error fetching address: $e');
    } finally {
      Navigator.of(context).pop(); // Close the loading indicator
    }

    return null; // Return null when the address is not available
  }
  void _showPopup(
      BuildContext context, double latitude, double longitude) async {
    String? address = await fetchAddress(latitude, longitude);

    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text('Location Info'),
          content: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Latitude: $latitude'),
              Text('Longitude: $longitude'),
              SizedBox(height: 10),
              if (address != null)
                Text('Address: $address'),
              if (address == null)
                Text('Address not available'),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
              },
              child: Text('Close'),
            ),
          ],
        );
      },
    );
  }

}
