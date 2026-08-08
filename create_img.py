from PIL import Image
import time

img = Image.new('RGB', (1080, 1920), color = 'red')
img.save('test_image.png')
print('test_image.png created')
