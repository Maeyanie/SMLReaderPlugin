from . import SMLReader

def getMetaData():
    return {
        "mesh_reader": [
            {
                "extension": "sml",
                "description": "SML File"
            }
        ]
    }


def register(app):
    return {"mesh_reader": SMLReader.SMLReader()}
