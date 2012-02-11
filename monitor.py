import os
import cgi

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api import mail
from google.appengine.api import urlfetch

class Location(db.Model):
	url = db.StringProperty(multiline=False)
	allowable_status_code = db.IntegerProperty()
	is_active = db.BooleanProperty()
	created_date = db.DateTimeProperty(auto_now_add=True)

class Watcher(db.Model):
	name = db.StringProperty(multiline=False)
	email = db.StringProperty(multiline=False)
	contact_threshold = db.IntegerProperty()
	is_active = db.BooleanProperty()

class FailureEvent(db.Model):
	references_location = db.ReferenceProperty(Location)
	received_code = db.IntegerProperty()
	is_valid = db.BooleanProperty()
	created_date = db.DateTimeProperty(auto_now_add=True)

class SuccessiveFailure(db.Model):
	references_location = db.ReferenceProperty(Location)
	failure_count = db.IntegerProperty()
	is_valid = db.BooleanProperty()
	updated_date = db.DateTimeProperty(auto_now_add=True)


class MainPage(webapp.RequestHandler):
	def get(self):
		self.response.out.write('<html><body>Beginning init<br/><br /><ul>')

		location_query = Location.all()
		locations = location_query.fetch(1)
		if 0 == len(locations):
			location = Location()
			location.url = "http://www.example.com"
			location.allowable_status_code = 200
			location.is_active = False
			location.put()
			self.response.out.write("<li>Created first location</li>")

		watchers_query = Watcher.all()
		watchers = watchers_query.fetch(1)
		if 0 == len(watchers):
			watcher = Watcher()
			watcher.name = 'Example'
			watcher.email = "example@example.com"
			watcher.contact_threshold = 0
			watcher.is_active = False
			watcher.put()
			self.response.out.write("<li>Created first watcher</li>")

		failures_query = FailureEvent.all()
		failures = failures_query.fetch(1)
		if 0 == len(failures):
			failure = FailureEvent()
			default_location = Location.all().filter("url =", "http://www.example.com").fetch(1)[0]
			failure.references_location = default_location
			failure.received_code = 999
			failure.is_valid = False
			failure.put()
			self.response.out.write("<li>Created first failure event</li>")

		successive_failures_query = SuccessiveFailure.all()
		successive_failures = successive_failures_query.fetch(1)
		if 0 == len(successive_failures):
			failure = SuccessiveFailure()
			default_location = Location.all().filter("url =", "http://www.example.com").fetch(1)[0]
			failure.references_location = default_location
			failure.failure_count = 0
			failure.is_valid = False
			failure.put()
			self.response.out.write("<li>Created first successive failure</li>")

		self.response.out.write('</ul><br/>Ending init</body></html>')

class Scan(webapp.RequestHandler):
	def get(self):
		self.response.out.write('<html><body>Beginning scan<br />')

		locations_query = Location.all().filter("is_active =", True)
		locations = locations_query.fetch(10000)

		for location in locations:
			self.response.out.write('url = ' + location.url + '<br />')	
			try:
				result = urlfetch.fetch(location.url)
				if location.allowable_status_code != result.status_code:
					self.response.out.write('failure: ' + str(result.status_code) + '<br/>')	
					failure = FailureEvent()	
					failure.references_location = location
					failure.is_valid = True
					failure.received_code = result.status_code
					failure.put()

					successive_failure_query = SuccessiveFailure.all().filter("references_location =", location)
					successive_failures = successive_failure_query.fetch(1)

					if 0 == len(successive_failures):
						successive_failure = SuccessiveFailure()
						successive_failure.references_location = location
						successive_failure.failure_count = 1
						successive_failure.is_valid = True
						successive_failure.put()
					else:
						successive_failure = successive_failures[0]
						successive_failure.failure_count += 1
						successive_failure.put()

				else:
					successive_failure_query = SuccessiveFailure.all().filter("references_location =", location)
					successive_failures = successive_failure_query.fetch(1)
					
					if 0 != len(successive_failures):
						successive_failures[0].failure_count = 0
						successive_failures[0].put()

			except IOError:
				self.response.out.write(e)

		self.response.out.write('<br />Ending scan</html></body>')
		self.contact()

	def contact(self):
		watchers = Watcher.all().filter("is_active =", True)

		for watcher in watchers:
			message = ''
			failures = SuccessiveFailure.all().filter("failure_count > ", watcher.contact_threshold)
			for failure in failures:
				if failure.references_location.is_active:
					message += "Location: " + failure.references_location.url + " | Successive Failure Count: " + str(failure.failure_count) + "\n"

			if 0 < len(message):
				self.response.out.write('<br />Contacting: ' + watcher.email + '<br />')
				mail.send_mail(sender="XTreme Monitor<xtrememonitor2@xtrememonitor2.appspotmail.com>",
										to = watcher.name + "<" + watcher.email + ">",
										subject = "Failure Threshold Exceeded",
										body=message)

application = webapp.WSGIApplication(
																			[('/', MainPage), ('/Scan', Scan)], 
																			debug=True)

def main():
	run_wsgi_app(application)

if __name__ == "__main__":
	main()
