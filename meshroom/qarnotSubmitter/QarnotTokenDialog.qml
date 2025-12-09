import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Window {
    id: root
    visible: true
    width: 450
    height: 250
    title: "Qarnot Render"
    
    x: (Screen.width - width) / 2
    y: (Screen.height - height) / 2
    
    flags: Qt.Dialog | Qt.WindowStaysOnTopHint
    modality: Qt.ApplicationModal 

    // Cette propriété sera remplie par Python
    property var palette

    // Signal et erreur
    signal acceptToken(string token)
    property string errorMessage: ""

    // --- FOND DE LA FENÊTRE ---
    // On utilise un Rectangle pour forcer la couleur de fond
    // car Window.color peut parfois être ignoré sous Windows/Mac
    Rectangle {
        anchors.fill: parent
        // On vérifie si 'palette' est défini, sinon on met gris par défaut
        color: root.palette ? root.palette.window : "#323437"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 10

        Label {
            text: "Entrez votre Token Qarnot :"
            color: root.palette ? root.palette.text : "white"
            font.bold: true
            font.pixelSize: 14
        }

        TextField {
            id: tokenField
            Layout.fillWidth: true
            placeholderText: "Votre API Token..."
            selectByMouse: true
            focus: true
            
            color: root.palette ? root.palette.text : "white"
            placeholderTextColor: root.palette ? root.palette.disabledText : "grey"
            
            background: Rectangle {
                color: root.palette ? root.palette.base : "#222"
                border.color: tokenField.activeFocus && root.palette ? root.palette.highlight : (root.palette ? root.palette.mid : "#555")
                border.width: tokenField.activeFocus ? 2 : 1
                radius: 4
            }
            
            onTextChanged: root.errorMessage = ""
            onAccepted: validateBtn.clicked()
        }

        Label {
            text: root.errorMessage
            visible: root.errorMessage !== ""
            color: "#ff5555"
            font.italic: true
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 10

            Button {
                text: "Annuler"
                contentItem: Text { 
                    text: parent.text; 
                    color: root.palette ? root.palette.text : "white"; 
                    horizontalAlignment: Text.AlignHCenter; 
                    verticalAlignment: Text.AlignVCenter 
                }
                background: Rectangle { 
                    color: parent.down && root.palette ? root.palette.mid : (root.palette ? root.palette.button : "#444"); 
                    radius: 4 
                }
                onClicked: root.close()
            }

            Button {
                id: validateBtn
                text: "Valider"
                enabled: tokenField.text.length > 0
                
                contentItem: Text {
                    text: parent.text
                    color: parent.enabled ? "white" : (root.palette ? root.palette.disabledText : "grey")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.bold: true
                }
                background: Rectangle {
                    // Bleu (Highlight)
                    color: parent.enabled ? 
                           (parent.down && root.palette ? Qt.darker(root.palette.highlight, 1.2) : (root.palette ? root.palette.highlight : "blue")) 
                           : (root.palette ? root.palette.button : "#444")
                    radius: 4
                }

                onClicked: root.acceptToken(tokenField.text)
            }
        }
    }
}